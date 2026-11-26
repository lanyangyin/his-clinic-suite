from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.modules.auth.security import require_read_login, require_role
from sqlalchemy import func

from app.modules.encounter.models import PrescriptionLine
from app.modules.insurance.adapter import InsuranceForbiddenError
from app.modules.patient.models import Patient
from app.modules.registration.models import Registration
from app.modules.tcm.models import TcmPrescription
from app.modules.billing.models import Payment
from app.modules.pharmacy.models import Dispense
from app.modules.charges.models import EncounterCharge
from sqlalchemy import func

from .schemas import (
    AdverseReactionCreate,
    AdverseReactionResponse,
    BarcodeLookup,
    DiagnosisUpdate,
    EncounterCreate,
    EncounterDiagnosisItem,
    EncounterDiagnosisResponse,
    EncounterResponse,
    MedicalRecordCreate,
    MedicalRecordResponse,
    MedicalRecordUpdate,
    PrescriptionBatchCreate,
    PrescriptionHeaderResponse,
    PrescriptionItemCreate,
    PrescriptionItemResponse,
    PrescriptionItemUpdate,
    PrescriptionReviewRequest,
    QualityResponse,
    RecordRevisionCreate,
    RecordRevisionResponse,
    RecordRevisionReview,
    ReturnEncounterRequest,
)
from .service import (
    EncounterClosedError,
    PrescriptionRuleError,
    abandon_encounter,
    add_prescription_item,
    create_encounter,
    create_medical_record,
    get_encounter,
    get_medical_record,
    get_medical_record_quality,
    list_encounter_diagnoses,
    list_encounters,
    list_medical_record_versions,
    list_prescription_headers,
    list_prescription_items,
    list_prescription_lines,
    list_record_revisions,
    request_record_revision,
    review_prescription,
    review_record_revision,
    upload_prescription_insurance,
    prescription_center,
    replace_encounter_diagnoses,
    sign_medical_record,
    update_diagnosis,
    update_medical_record,
    update_prescription_item,
    worklist,
    encounter_summary,
    pause_encounter,
    resume_encounter,
    return_encounter,
    record_adverse_reaction,
    list_adverse_reactions,
)

router = APIRouter(prefix="/encounters", tags=["encounters"], dependencies=[Depends(require_read_login)])


@router.post("/", response_model=EncounterResponse, status_code=201)
def create(
    data: EncounterCreate,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("doctor")),
):
    try:
        return create_encounter(db, data)
    except ValueError as e:
        code = 400 if ("诊断编码" in str(e) or "尚未完成" in str(e)) else 404
        raise HTTPException(status_code=code, detail=str(e))


@router.get("/", response_model=list[EncounterResponse])
def get_all(patient_id: int | None = None, db: Session = Depends(get_db)):
    return list_encounters(db, patient_id)


@router.get("/worklist")
def get_worklist(
    db: Session = Depends(get_db),
    user=Depends(require_role("doctor")),
):
    """医生门诊工作台队列：绑定医生账号只看本人，未绑定则保持全院视图。"""
    return worklist(db, doctor_id=getattr(user, "doctor_id", None))


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


@router.get(
    "/{encounter_id}/diagnoses",
    response_model=list[EncounterDiagnosisResponse],
)
def get_diagnoses(encounter_id: int, db: Session = Depends(get_db)):
    return list_encounter_diagnoses(db, encounter_id)


@router.put(
    "/{encounter_id}/diagnoses",
    response_model=list[EncounterDiagnosisResponse],
)
def set_diagnoses(
    encounter_id: int,
    data: list[EncounterDiagnosisItem],
    db: Session = Depends(get_db),
    user=Depends(require_role("doctor")),
):
    try:
        return replace_encounter_diagnoses(db, encounter_id, data, user.username)
    except EncounterClosedError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


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


@router.post("/start", response_model=EncounterResponse, status_code=201)
def start_consultation(
    data: EncounterCreate,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("doctor")),
):
    try:
        return create_encounter(db, data, enforce_lock=True)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{encounter_id}/pause", response_model=EncounterResponse)
def pause_visit(
    encounter_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("doctor", "admin")),
):
    try:
        return pause_encounter(db, encounter_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{encounter_id}/abandon", response_model=EncounterResponse)
def abandon_visit(
    encounter_id: int,
    reason: str = "",
    db: Session = Depends(get_db),
    user=Depends(require_role("doctor", "admin")),
):
    try:
        return abandon_encounter(db, encounter_id, reason)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{encounter_id}/resume", response_model=EncounterResponse)
def resume_visit(
    encounter_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("doctor", "admin")),
):
    try:
        return resume_encounter(db, encounter_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{encounter_id}/return", response_model=EncounterResponse, status_code=201)
def return_visit(
    encounter_id: int,
    data: ReturnEncounterRequest,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("doctor", "admin")),
):
    """已收费回诊：同一挂号下新建回诊就诊，不重新挂号。"""
    try:
        return return_encounter(
            db, encounter_id, diagnosis=data.diagnosis, diagnosis_code=data.diagnosis_code
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/{encounter_id}/adverse-reactions",
    response_model=AdverseReactionResponse,
    status_code=201,
)
def create_adverse_reaction(
    encounter_id: int,
    data: AdverseReactionCreate,
    db: Session = Depends(get_db),
    user=Depends(require_role("doctor", "admin")),
):
    try:
        return record_adverse_reaction(db, encounter_id, data, user.username)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "/{encounter_id}/adverse-reactions",
    response_model=list[AdverseReactionResponse],
)
def adverse_reactions(encounter_id: int, db: Session = Depends(get_db)):
    return list_adverse_reactions(db, encounter_id)


@router.post(
    "/{encounter_id}/medical-record/revisions",
    response_model=RecordRevisionResponse,
    status_code=201,
)
def request_revision(
    encounter_id: int,
    data: RecordRevisionCreate,
    db: Session = Depends(get_db),
    user=Depends(require_role("doctor")),
):
    try:
        return request_record_revision(db, encounter_id, data.reason, user.username)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/medical-record-revisions", response_model=list[RecordRevisionResponse])
def record_revisions(
    status: str | None = None,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("admin", "director")),
):
    return list_record_revisions(db, status)


@router.post(
    "/medical-record-revisions/{revision_id}/review",
    response_model=RecordRevisionResponse,
)
def review_revision(
    revision_id: int,
    data: RecordRevisionReview,
    db: Session = Depends(get_db),
    user=Depends(require_role("admin", "director")),
):
    try:
        return review_record_revision(
            db, revision_id, data.approve, user.username, data.note
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{encounter_id}", response_model=EncounterResponse)
def get_one(encounter_id: int, db: Session = Depends(get_db)):
    encounter = get_encounter(db, encounter_id)
    if not encounter:
        raise HTTPException(status_code=404, detail="就诊记录不存在")
    return encounter


@router.get("/{encounter_id}/prescription-center")
def get_prescription_center(
    encounter_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_role("doctor", "nurse", "cashier", "pharmacist", "admin")),
):
    try:
        return prescription_center(db, encounter_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{encounter_id}/prescription-lines")
def prescription_lines(
    encounter_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_role("doctor", "nurse", "cashier", "pharmacist", "admin")),
):
    return [
        {
            "id": row.id,
            "prescription_id": row.prescription_id,
            "kind": row.kind,
            "drug_id": row.drug_id,
            "herb_id": row.herb_id,
            "name": row.name,
            "spec": row.spec,
            "quantity": row.quantity,
            "unit": row.unit,
            "dosage": row.dosage,
            "frequency": row.frequency,
            "route": row.route,
            "days": row.days,
            "unit_price": row.unit_price,
            "amount": row.amount,
        }
        for row in list_prescription_lines(db, encounter_id)
    ]


@router.get(
    "/{encounter_id}/prescriptions/headers",
    response_model=list[PrescriptionHeaderResponse],
)
def prescription_headers(encounter_id: int, db: Session = Depends(get_db)):
    rows = list_prescription_headers(db, encounter_id)
    counts = dict(
        db.query(PrescriptionLine.prescription_id, func.count(PrescriptionLine.id))
        .filter(PrescriptionLine.prescription_id.in_([row.id for row in rows]))
        .group_by(PrescriptionLine.prescription_id)
        .all()
    )
    return [
        PrescriptionHeaderResponse.model_validate(row).model_copy(
            update={"item_count": counts.get(row.id) or len(row.items)}
        )
        for row in rows
    ]


@router.post(
    "/{encounter_id}/prescriptions/{prescription_id}/insurance-upload",
    response_model=PrescriptionHeaderResponse,
)
def insurance_upload(
    encounter_id: int,
    prescription_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_role("cashier", "doctor", "pharmacist")),
):
    try:
        row = upload_prescription_insurance(
            db, encounter_id, prescription_id, user.username
        )
        return PrescriptionHeaderResponse.model_validate(row).model_copy(
            update={"item_count": len(row.items)}
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/{encounter_id}/prescriptions/{prescription_id}/review",
    response_model=PrescriptionHeaderResponse,
)
def review_prescription_header(
    encounter_id: int,
    prescription_id: int,
    data: PrescriptionReviewRequest,
    db: Session = Depends(get_db),
    user=Depends(require_role("pharmacist")),
):
    try:
        row = review_prescription(
            db,
            encounter_id,
            prescription_id,
            data.approve,
            data.note,
            user.username,
        )
        return PrescriptionHeaderResponse.model_validate(row).model_copy(
            update={"item_count": len(row.items)}
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


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
    user=Depends(require_role("doctor")),
):
    try:
        return update_medical_record(db, encounter_id, data, user.username)
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


@router.get("/{encounter_id}/medical-record/versions")
def medical_record_versions(
    encounter_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("doctor", "admin")),
):
    try:
        rows = list_medical_record_versions(db, encounter_id)
        return [
            {
                "id": row.id,
                "version": row.version,
                "action": row.action,
                "changed_by": row.changed_by,
                "before_json": row.before_json,
                "after_json": row.after_json,
                "created_at": row.created_at,
            }
            for row in rows
        ]
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get(
    "/{encounter_id}/medical-record/quality", response_model=QualityResponse
)
def medical_record_quality(encounter_id: int, db: Session = Depends(get_db)):
    try:
        return get_medical_record_quality(db, encounter_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.put(
    "/{encounter_id}/prescriptions/items/{item_id}",
    response_model=PrescriptionItemResponse,
)
def edit_prescription_item(
    encounter_id: int,
    item_id: int,
    data: PrescriptionItemUpdate,
    db: Session = Depends(get_db),
    user=Depends(require_role("doctor")),
):
    try:
        return update_prescription_item(db, encounter_id, item_id, data, user.username)
    except ValueError as e:
        code = 409 if isinstance(e, EncounterClosedError) else 400
        raise HTTPException(status_code=code, detail=str(e))


@router.delete("/{encounter_id}/prescriptions/{item_id}", status_code=204)
def remove_prescription(
    encounter_id: int,
    item_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("doctor")),
):
    from .service import delete_prescription_item

    try:
        delete_prescription_item(db, encounter_id, item_id)
    except EncounterClosedError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
        code = 400 if "病历已签名" in str(e) else 404
        raise HTTPException(status_code=code, detail=str(e))


@router.post(
    "/{encounter_id}/prescriptions/batch",
    response_model=list[PrescriptionItemResponse],
    status_code=201,
)
def add_items_batch(
    encounter_id: int,
    data: PrescriptionBatchCreate,
    db: Session = Depends(get_db),
    user=Depends(require_role("doctor")),
):
    from .service import add_prescription_items_batch

    try:
        return add_prescription_items_batch(
            db, encounter_id, data.items, user.username
        )
    except EncounterClosedError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except PrescriptionRuleError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except InsuranceForbiddenError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


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
        code = 400 if "病历已签名" in str(e) else 404
        raise HTTPException(status_code=code, detail=str(e))
