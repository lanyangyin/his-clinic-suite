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


def add_prescription_item(
    db: Session, encounter_id: int, data: PrescriptionItemCreate
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
