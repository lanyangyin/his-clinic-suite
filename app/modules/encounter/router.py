from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.modules.auth.security import require_role
from app.modules.insurance.adapter import InsuranceForbiddenError
from app.modules.patient.models import Patient
from app.modules.registration.models import Registration
from app.modules.tcm.models import TcmPrescription
from app.modules.billing.models import Payment
from app.modules.pharmacy.models import Dispense
from app.modules.charges.models import EncounterCharge
from sqlalchemy import func

from .schemas import (
    BarcodeLookup,
    DiagnosisUpdate,
    EncounterCreate,
    EncounterResponse,
    MedicalRecordCreate,
    MedicalRecordResponse,
    MedicalRecordUpdate,
    PrescriptionItemCreate,
    PrescriptionItemResponse,
    QualityResponse,
)
from .service import (
    EncounterClosedError,
    PrescriptionRuleError,
    add_prescription_item,
    create_encounter,
    create_medical_record,
    get_encounter,
    get_medical_record,
    get_medical_record_quality,
    list_encounters,
    list_prescription_items,
    sign_medical_record,
    update_diagnosis,
    update_medical_record,
    worklist,
    encounter_summary,
)

router = APIRouter(prefix="/encounters", tags=["encounters"])


@router.post("/", response_model=EncounterResponse, status_code=201)
def create(
    data: EncounterCreate,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("doctor")),
):
    try:
        return create_encounter(db, data)
    except ValueError as e:
        code = 400 if "诊断编码" in str(e) else 404
        raise HTTPException(status_code=code, detail=str(e))


@router.get("/", response_model=list[EncounterResponse])
def get_all(patient_id: int | None = None, db: Session = Depends(get_db)):
    return list_encounters(db, patient_id)


@router.get("/worklist")
def get_worklist(
    db: Session = Depends(get_db),
    _: None = Depends(require_role("doctor")),
):
    """医生门诊工作台队列：待接诊 + 今日已接诊。"""
    return worklist(db)


@router.get("/by-barcode/{code}", response_model=BarcodeLookup)
def lookup_by_barcode(
    code: str,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("cashier", "pharmacist", "doctor", "nurse", "admin")),
):
    """扫码枪解析处方条码：RX000201 / TCM2026... / 就诊ID。"""
    normalized = code.strip().upper()
    encounter_id = None
    code_type = ""
    if normalized.startswith("RX") and normalized[2:].isdigit():
        encounter_id = int(normalized[2:])
        code_type = "western"
    elif normalized.startswith("TCM"):
        rx = (
            db.query(TcmPrescription)
            .filter(TcmPrescription.prescription_no == normalized)
            .first()
        )
        if rx:
            encounter_id = rx.encounter_id
            code_type = "tcm"
    elif normalized.startswith("ENC") and normalized[3:].isdigit():
        encounter_id = int(normalized[3:])
        code_type = "encounter"
    elif normalized.isdigit():
        encounter_id = int(normalized)
        code_type = "encounter"
    if not encounter_id:
        raise HTTPException(status_code=404, detail="条码格式不正确或处方不存在")
    encounter = get_encounter(db, encounter_id)
    if not encounter:
        raise HTTPException(status_code=404, detail="条码对应就诊不存在")
    registration = db.get(Registration, encounter.registration_id)
    patient = db.get(Patient, registration.patient_id) if registration else None
    payment = (
        db.query(Payment).filter(Payment.encounter_id == encounter.id).first()
    )
    is_paid = bool(payment and payment.status == "paid")
    dispense = (
        db.query(Dispense).filter(Dispense.encounter_id == encounter.id).first()
    )
    is_dispensed = bool(dispense and dispense.status == "dispensed")
    pending_amount = float(
        db.query(func.coalesce(func.sum(EncounterCharge.amount), 0))
        .filter(
            EncounterCharge.encounter_id == encounter.id,
            EncounterCharge.status == "pending",
        )
        .scalar()
        or 0
    )
    if not is_paid:
        status_text = "未收费，不能发药"
    elif is_dispensed:
        status_text = "已发药"
    else:
        status_text = "已收费，可发药"
    return BarcodeLookup(
        encounter_id=encounter.id,
        patient_id=patient.id if patient else 0,
        patient_name=patient.name if patient else "",
        code=normalized,
        code_type=code_type,
        is_paid=is_paid,
        is_dispensed=is_dispensed,
        pending_amount=round(pending_amount, 2),
        status_text=status_text,
    )


@router.put("/{encounter_id}/diagnosis", response_model=EncounterResponse)
def set_diagnosis(
    encounter_id: int,
    data: DiagnosisUpdate,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("doctor")),
):
    try:
        return update_diagnosis(
            db, encounter_id, data.diagnosis_code, data.diagnosis
        )
    except EncounterClosedError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{encounter_id}", response_model=EncounterResponse)
def get_one(encounter_id: int, db: Session = Depends(get_db)):
    encounter = get_encounter(db, encounter_id)
    if not encounter:
        raise HTTPException(status_code=404, detail="就诊记录不存在")
    return encounter


@router.get(
    "/{encounter_id}/prescriptions", response_model=list[PrescriptionItemResponse]
)
def list_items(encounter_id: int, db: Session = Depends(get_db)):
    if not get_encounter(db, encounter_id):
        raise HTTPException(status_code=404, detail="就诊记录不存在")
    return list_prescription_items(db, encounter_id)


@router.get("/{encounter_id}/summary")
def get_summary(
    encounter_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("doctor")),
):
    data = encounter_summary(db, encounter_id)
    if not data:
        raise HTTPException(status_code=404, detail="就诊记录不存在")
    return data


_NOT_FOUND = {"就诊记录不存在", "该就诊还没有病历"}


@router.post(
    "/{encounter_id}/medical-record",
    response_model=MedicalRecordResponse,
    status_code=201,
)
def new_medical_record(
    encounter_id: int,
    data: MedicalRecordCreate,
    db: Session = Depends(get_db),
    user=Depends(require_role("doctor")),
):
    try:
        return create_medical_record(db, encounter_id, data, user.username)
    except ValueError as e:
        code = 404 if str(e) in _NOT_FOUND else 400
        raise HTTPException(status_code=code, detail=str(e))


@router.get("/{encounter_id}/medical-record", response_model=MedicalRecordResponse)
def get_medical_record_one(encounter_id: int, db: Session = Depends(get_db)):
    record = get_medical_record(db, encounter_id)
    if not record:
        raise HTTPException(status_code=404, detail="病历不存在")
    return record


@router.put("/{encounter_id}/medical-record", response_model=MedicalRecordResponse)
def update_medical_record_one(
    encounter_id: int,
    data: MedicalRecordUpdate,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("doctor")),
):
    try:
        return update_medical_record(db, encounter_id, data)
    except ValueError as e:
        code = 404 if str(e) in _NOT_FOUND else 400
        raise HTTPException(status_code=code, detail=str(e))


@router.post(
    "/{encounter_id}/medical-record/sign", response_model=MedicalRecordResponse
)
def sign_record(
    encounter_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_role("doctor")),
):
    try:
        return sign_medical_record(db, encounter_id, user.username)
    except ValueError as e:
        code = 404 if str(e) == "病历不存在" else 400
        raise HTTPException(status_code=code, detail=str(e))


@router.get(
    "/{encounter_id}/medical-record/quality", response_model=QualityResponse
)
def medical_record_quality(encounter_id: int, db: Session = Depends(get_db)):
    try:
        return get_medical_record_quality(db, encounter_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post(
    "/{encounter_id}/prescriptions",
    response_model=PrescriptionItemResponse,
    status_code=201,
)
def add_item(
    encounter_id: int,
    data: PrescriptionItemCreate,
    db: Session = Depends(get_db),
    user=Depends(require_role("doctor")),
):
    try:
        return add_prescription_item(db, encounter_id, data, user.username)
    except EncounterClosedError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except PrescriptionRuleError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except InsuranceForbiddenError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
