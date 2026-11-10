from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.modules.charges.service import (
    CONSULTATION_FEE_CODE,
    REGISTRATION_FEE_CODE,
    add_charge,
    add_dict_fee,
)
from app.modules.drug.service import get_drug
from app.modules.insurance_catalog.service import resolve_prescription_insurance
from app.modules.insurance.adapter import (
    InsuranceForbiddenError,
    InsuranceUnavailable,
    check_prescription,
)
from app.modules.patient.allergy import allergy_conflict
from app.modules.patient.service import get_patient
from app.modules.registration.service import (
    get_patient_registration_ids,
    get_registration,
    mark_registration_visited,
)
from app.modules.triage.service import complete_ticket_for_registration

from .models import Encounter, MedicalRecord, PrescriptionItem
from .schemas import (
    EncounterCreate,
    MedicalRecordCreate,
    MedicalRecordUpdate,
    PrescriptionItemCreate,
)


class EncounterClosedError(Exception):
    """就诊已关闭（已收费）时仍试图修改处方。"""


class PrescriptionRuleError(ValueError):
    """合理用药规则拦截（重复用药/抗菌药物分级）。"""


def _resolve_diagnosis(db: Session, code: str, name: str) -> tuple[str, str]:
    """校验 ICD-10 编码；只填名称时尝试精确匹配常用字典。"""
    from app.modules.dict.service import get_entry, list_entries

    code = (code or "").strip()
    name = (name or "").strip()
    if code:
        entry = get_entry(db, "diagnosis_icd10", code)
        if not entry or not entry.active:
            raise ValueError(f"诊断编码不存在或已停用：{code}")
        return code, name or entry.name
    if name:
        for entry in list_entries(db, "diagnosis_icd10", active_only=True):
            if entry.name == name:
                return entry.code, name
    return "", name


def create_encounter(db: Session, data: EncounterCreate) -> Encounter:
    """接诊：挂号存在且未就诊时创建就诊记录，并把挂号置为 visited。

    同一挂号重复调用时返回已有的就诊记录（幂等）。
    """
    registration = get_registration(db, data.registration_id)
    if not registration:
        raise ValueError("挂号记录不存在")

    existing = (
        db.query(Encounter)
        .filter(Encounter.registration_id == data.registration_id)
        .first()
    )
    if existing:
        return existing

    encounter = Encounter(
        registration_id=data.registration_id,
        diagnosis=data.diagnosis,
        diagnosis_code=data.diagnosis_code,
    )
    encounter.diagnosis_code, encounter.diagnosis = _resolve_diagnosis(
        db, data.diagnosis_code, data.diagnosis
    )
    db.add(encounter)
    mark_registration_visited(db, registration)
    complete_ticket_for_registration(db, data.registration_id)
    db.flush()

    # 计费：挂号费 + 诊疗费（字典存在才计费，兼容存量数据）
    add_dict_fee(
        db,
        encounter_id=encounter.id,
        code=REGISTRATION_FEE_CODE,
        source_type="registration",
        source_id=registration.id,
    )
    add_dict_fee(
        db,
        encounter_id=encounter.id,
        code=CONSULTATION_FEE_CODE,
        source_type="encounter",
        source_id=encounter.id,
    )

    db.commit()
    db.refresh(encounter)
    return encounter


def update_diagnosis(
    db: Session, encounter_id: int, diagnosis_code: str, diagnosis: str
) -> Encounter:
    encounter = db.get(Encounter, encounter_id)
    if not encounter:
        raise ValueError("就诊记录不存在")
    if encounter.status == "closed":
        raise EncounterClosedError("就诊已收费，不能再修改诊断")
    code, name = _resolve_diagnosis(db, diagnosis_code, diagnosis)
    encounter.diagnosis_code = code
    encounter.diagnosis = name
    db.commit()
    db.refresh(encounter)
    return encounter


def add_prescription_item(
    db: Session, encounter_id: int, data: PrescriptionItemCreate, operator: str = ""
) -> PrescriptionItem:
    """给就诊添加一条处方明细：单价取药品基准价（快照进明细）。

    已关闭（已收费）的就诊不能再开处方。
    """
    encounter = db.get(Encounter, encounter_id)
    if not encounter:
        raise ValueError("就诊记录不存在")

    if encounter.status == "closed":
        raise EncounterClosedError("就诊已收费，不能再开处方")

    drug = get_drug(db, data.drug_id)
    if not drug:
        raise ValueError("药品不存在")

    # 合理用药：重复开立同一药品拦截
    existing_item = (
        db.query(PrescriptionItem)
        .filter(
            PrescriptionItem.encounter_id == encounter_id,
            PrescriptionItem.drug_id == data.drug_id,
        )
        .first()
    )
    if existing_item:
        raise PrescriptionRuleError("该药品已在处方中，请勿重复开立")

    # 合理用药：特殊使用级抗菌药物需会诊审批
    if drug.antibiotic_level == 3:
        raise PrescriptionRuleError("特殊使用级抗菌药物需会诊审批，暂不允许开立")

    # 过敏史硬拦截：命中必须由医生填写 override 理由，留下操作人
    allergy_warning = None
    registration = get_registration(db, encounter.registration_id)
    patient = get_patient(db, registration.patient_id) if registration else None
    if patient and patient.allergy_status == "present":
        conflict = allergy_conflict(patient.allergy_detail, drug.name)
        if conflict:
            reason = (data.allergy_override_reason or "").strip()
            if not reason:
                raise PrescriptionRuleError(
                    f"{conflict}。如确认可继续使用，请填写 override 理由后重试"
                )
            allergy_warning = conflict

    # 医保目录校验：按贯标码/名称+剂型+规格确定甲乙丙类与报销比例
    category, insurance_ratio, catalog_warning = resolve_prescription_insurance(db, drug)

    # 医保事前提醒：同步阻塞调用（禁止→拒开，提醒→记录，不可用→降级放行）
    try:
        review = check_prescription(
            diagnosis=encounter.diagnosis,
            drug_name=drug.name,
            quantity=data.quantity,
            ratio=insurance_ratio,
        )
    except InsuranceUnavailable:
        warning = "医保服务不可用，已按自费放行"
    else:
        if review["result"] == "forbid":
            if insurance_ratio <= 0 and catalog_warning:
                # 目录内丙类/目录外（已对码）：允许自费开方，不拦截
                warning = catalog_warning
            else:
                raise InsuranceForbiddenError(review["message"])
        else:
            warning = review["message"] if review["result"] == "warn" else None

    warnings: list[str] = []
    for text in (catalog_warning, warning):
        if text and text not in warnings:
            warnings.append(text)
    item = PrescriptionItem(
        encounter_id=encounter_id,
        drug_id=data.drug_id,
        quantity=data.quantity,
        unit_price=drug.base_price,
        dosage=data.dosage,
        frequency=data.frequency,
        route=data.route,
        days=data.days,
        insurance_warning="；".join(warnings) or None,
        insurance_category=category,
        allergy_warning=allergy_warning,
        allergy_override_reason=(
            (data.allergy_override_reason or "").strip() if allergy_warning else None
        ),
        allergy_override_by=operator if allergy_warning else None,
    )
    db.add(item)
    db.flush()

    # 计费：药品费（单价快照 + 医保比例快照）
    add_charge(
        db,
        encounter_id=encounter_id,
        source_type="prescription",
        source_id=item.id,
        charge_type="drug",
        item_name=drug.name,
        quantity=data.quantity,
        unit_price=drug.base_price,
        insurance_ratio=insurance_ratio,
        drug_id=drug.id,
    )

    db.commit()
    db.refresh(item)
    return item


def get_encounter(db: Session, encounter_id: int) -> Encounter | None:
    """按 ID 查询就诊记录；不存在时返回 None。"""
    return db.get(Encounter, encounter_id)


def list_encounters(db: Session, patient_id: int | None = None) -> list[Encounter]:
    """就诊列表（可按患者过滤，最新在前）。"""
    query = db.query(Encounter)
    if patient_id is not None:
        registration_ids = get_patient_registration_ids(db, patient_id)
        if not registration_ids:
            return []
        query = query.filter(Encounter.registration_id.in_(registration_ids))
    return query.order_by(Encounter.id.desc()).all()


def close_encounter(db: Session, encounter: Encounter) -> None:
    """把就诊状态改为 closed（只改内存，由调用方统一 commit）。"""
    encounter.status = "closed"


def list_prescription_items(
    db: Session, encounter_id: int
) -> list[PrescriptionItem]:
    """就诊的全部处方明细（可能为空列表）。"""
    return (
        db.query(PrescriptionItem)
        .filter(PrescriptionItem.encounter_id == encounter_id)
        .all()
    )


def get_encounter_total(db: Session, encounter_id: int) -> float:
    """就诊处方总金额：sum(quantity * unit_price)。"""
    total = (
        db.query(func.sum(PrescriptionItem.quantity * PrescriptionItem.unit_price))
        .filter(PrescriptionItem.encounter_id == encounter_id)
        .scalar()
    )
    return float(total or 0)


def create_medical_record(
    db: Session, encounter_id: int, data: MedicalRecordCreate, written_by: str = ""
) -> MedicalRecord:
    """书写门诊结构化病历：一次就诊一份，收费关闭后不可书写。"""
    encounter = get_encounter(db, encounter_id)
    if not encounter:
        raise ValueError("就诊记录不存在")
    if encounter.status == "closed":
        raise ValueError("就诊已关闭，不能书写病历")

    existing = (
        db.query(MedicalRecord)
        .filter(MedicalRecord.encounter_id == encounter_id)
        .first()
    )
    if existing:
        raise ValueError("该就诊已有病历")

    record = MedicalRecord(
        encounter_id=encounter_id,
        written_by=written_by,
        **data.model_dump(),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def get_medical_record(db: Session, encounter_id: int) -> MedicalRecord | None:
    return (
        db.query(MedicalRecord)
        .filter(MedicalRecord.encounter_id == encounter_id)
        .first()
    )


def update_medical_record(
    db: Session, encounter_id: int, data: MedicalRecordUpdate
) -> MedicalRecord:
    """修改病历：就诊关闭或病历已签名后不可修改。"""
    encounter = get_encounter(db, encounter_id)
    if not encounter:
        raise ValueError("就诊记录不存在")
    if encounter.status == "closed":
        raise ValueError("就诊已关闭，不能修改病历")

    record = get_medical_record(db, encounter_id)
    if not record:
        raise ValueError("该就诊还没有病历")
    if record.signed_at:
        raise ValueError("病历已签名，不能修改")

    for field, value in data.model_dump(exclude_none=True).items():
        setattr(record, field, value)
    record.updated_at = datetime.now()
    db.commit()
    db.refresh(record)
    return record


def sign_medical_record(
    db: Session, encounter_id: int, signed_by: str = ""
) -> MedicalRecord:
    """电子签名：签名后病历锁定（已签名病历不可再签）。"""
    record = get_medical_record(db, encounter_id)
    if not record:
        raise ValueError("病历不存在")
    if record.signed_at:
        raise ValueError("病历已签名")

    record.signed_by = signed_by
    record.signed_at = datetime.now()
    db.commit()
    db.refresh(record)
    return record


def get_medical_record_quality(db: Session, encounter_id: int) -> dict:
    """病历质控评分：五项要点各 20 分，60 分及格。"""
    record = get_medical_record(db, encounter_id)
    if not record:
        raise ValueError("病历不存在")

    fields = [
        ("主诉", record.chief_complaint),
        ("现病史", record.present_illness),
        ("既往史", record.past_history),
        ("查体", record.physical_exam),
        ("处理意见", record.treatment_advice),
    ]
    missing = [name for name, value in fields if not (value or "").strip()]
    filled = len(fields) - len(missing)
    score = round(filled / len(fields) * 100)
    return {
        "score": score,
        "passed": score >= 60,
        "missing_fields": missing,
    }

def worklist(db: Session) -> list[dict]:
    """医生门诊队列：待接诊 + 今日已接诊，带费用预览。"""
    from datetime import date

    from app.modules.charges.service import list_charges
    from app.modules.patient.models import Patient
    from app.modules.registration.models import Registration
    from app.modules.staff.models import Doctor
    from app.modules.triage.models import TriageTicket

    rows = (
        db.query(Registration, Patient, Doctor)
        .join(Patient, Registration.patient_id == Patient.id)
        .join(Doctor, Registration.doctor_id == Doctor.id)
        .order_by(Registration.id.desc())
        .all()
    )
    result = []
    for registration, patient, doctor in rows:
        encounter = (
            db.query(Encounter)
            .filter(Encounter.registration_id == registration.id)
            .first()
        )
        if encounter is None and registration.status != "registered":
            continue
        if encounter is not None and encounter.created_at.date() != date.today():
            continue
        charges = list_charges(db, encounter.id) if encounter else []
        total = round(sum(row.amount for row in charges), 2)
        pending = round(sum(row.amount for row in charges if row.status == "pending"), 2)
        ticket = (
            db.query(TriageTicket)
            .filter(TriageTicket.registration_id == registration.id)
            .first()
        )
        result.append(
            {
                "registration_id": registration.id,
                "patient_id": patient.id,
                "patient_no": patient.patient_no,
                "patient_name": patient.name,
                "gender": patient.gender,
                "age": patient.age,
                "birth_date": patient.birth_date,
                "allergy_label": patient.allergy_label,
                "triage_level": ticket.triage_level if ticket else None,
                "temperature": ticket.temperature if ticket else None,
                "pulse": ticket.pulse if ticket else None,
                "respiration": ticket.respiration if ticket else None,
                "systolic": ticket.systolic if ticket else None,
                "diastolic": ticket.diastolic if ticket else None,
                "spo2": ticket.spo2 if ticket else None,
                "chief_complaint": ticket.chief_complaint if ticket else "",
                "isolation": ticket.isolation if ticket else False,
                "vital_summary": ticket.vital_summary if ticket else "",
                "doctor_id": doctor.id,
                "doctor_name": doctor.name,
                "registration_status": registration.status,
                "encounter_id": encounter.id if encounter else None,
                "encounter_status": encounter.status if encounter else "",
                "diagnosis": encounter.diagnosis if encounter else "",
                "diagnosis_code": encounter.diagnosis_code if encounter else "",
                "total_amount": total,
                "pending_amount": pending,
            }
        )
    result.sort(key=lambda row: (row["encounter_id"] is not None, row["registration_id"]))
    return result


def encounter_summary(db: Session, encounter_id: int) -> dict | None:
    from app.modules.charges.service import list_charges
    from app.modules.lis.service import list_requests
    from app.modules.patient.service import get_patient
    from app.modules.registration.service import get_registration
    from app.modules.staff.service import get_doctor
    from app.modules.treatment.service import list_treatments

    encounter = get_encounter(db, encounter_id)
    if not encounter:
        return None
    registration = get_registration(db, encounter.registration_id)
    patient = get_patient(db, registration.patient_id) if registration else None
    doctor = get_doctor(db, registration.doctor_id) if registration else None
    charges = list_charges(db, encounter.id)
    record = get_medical_record(db, encounter.id)
    return {
        "encounter_id": encounter.id,
        "registration_id": encounter.registration_id,
        "patient_id": patient.id if patient else None,
        "patient_name": patient.name if patient else "",
        "doctor_name": doctor.name if doctor else "",
        "diagnosis": encounter.diagnosis,
        "diagnosis_code": encounter.diagnosis_code,
        "status": encounter.status,
        "record_signed": bool(record and record.signed_by),
        "total_amount": round(sum(row.amount for row in charges), 2),
        "pending_amount": round(
            sum(row.amount for row in charges if row.status == "pending"), 2
        ),
        "charges": [
            {
                "id": row.id,
                "item_name": row.item_name,
                "quantity": row.quantity,
                "amount": row.amount,
                "status": row.status,
            }
            for row in charges
        ],
        "prescription_count": len(list_prescription_items(db, encounter.id)),
        "lab_count": len(list_requests(db, encounter.id)),
        "treatment_count": len(list_treatments(db, encounter.id)),
    }
