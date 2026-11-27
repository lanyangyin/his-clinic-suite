import json
from datetime import datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app import settings
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

from .models import (
    AdverseReaction,
    Encounter,
    EncounterDiagnosis,
    MedicalRecord,
    MedicalRecordRevision,
    MedicalRecordVersion,
    Prescription,
    PrescriptionItem,
    PrescriptionLine,
)
from .schemas import (
    EncounterCreate,
    EncounterDiagnosisItem,
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


def create_encounter(
    db: Session, data: EncounterCreate, enforce_lock: bool = False
) -> Encounter:
    """接诊：挂号存在且未就诊时创建就诊记录，并把挂号置为 visited。

    同一挂号重复调用时返回已有的就诊记录（幂等）。
    """
    registration = get_registration(db, data.registration_id)
    if not registration:
        raise ValueError("挂号记录不存在")

    if registration.status == "cancelled":
        raise ValueError("该挂号已取消，不能接诊；请重新挂号")
    existing = (
        db.query(Encounter)
        .filter(Encounter.registration_id == data.registration_id)
        .order_by(Encounter.id.desc())
        .first()
    )
    # 放弃接诊后允许同一挂号重新接诊（保留原放弃记录）；其余已有就诊保持幂等。
    if existing and existing.status != "abandoned":
        return existing
    if registration.status != "registered" and not (
        existing and existing.status == "abandoned"
    ):
        raise ValueError("该挂号不是待就诊状态，不能接诊")

    from app.modules.staff.models import Doctor

    doctor = db.get(Doctor, registration.doctor_id)
    if enforce_lock and doctor and doctor.current_encounter_id:
        current = db.get(Encounter, doctor.current_encounter_id)
        if current and current.status == "open":
            raise ValueError(
                "当前患者尚未完成诊治，请先完成或挂起当前患者，再开始下一位"
            )

    original_encounter = None
    if registration.original_registration_id:
        original_encounter = (
            db.query(Encounter)
            .filter(Encounter.registration_id == registration.original_registration_id)
            .order_by(Encounter.id.desc())
            .first()
        )
    encounter = Encounter(
        registration_id=data.registration_id,
        diagnosis=data.diagnosis,
        diagnosis_code=data.diagnosis_code,
        visit_type=registration.visit_type or "initial",
        original_encounter_id=original_encounter.id if original_encounter else None,
    )
    encounter.diagnosis_code, encounter.diagnosis = _resolve_diagnosis(
        db, data.diagnosis_code, data.diagnosis
    )
    db.add(encounter)
    db.flush()
    if encounter.diagnosis:
        db.add(
            EncounterDiagnosis(
                encounter_id=encounter.id,
                diagnosis_code=encounter.diagnosis_code,
                diagnosis=encounter.diagnosis,
                diagnosis_type="primary",
                sort_no=0,
            )
        )
    mark_registration_visited(db, registration)
    complete_ticket_for_registration(db, data.registration_id)
    db.flush()
    if doctor:
        doctor.current_encounter_id = encounter.id

    # 计费：初诊收挂号费；复诊免挂号费，仍收诊疗费（字典存在才计费）
    if registration.visit_type != "follow_up":
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


def list_encounter_diagnoses(
    db: Session, encounter_id: int
) -> list[EncounterDiagnosis]:
    return (
        db.query(EncounterDiagnosis)
        .filter(EncounterDiagnosis.encounter_id == encounter_id)
        .order_by(EncounterDiagnosis.sort_no, EncounterDiagnosis.id)
        .all()
    )


def replace_encounter_diagnoses(
    db: Session,
    encounter_id: int,
    items: list[EncounterDiagnosisItem],
    operator: str = "",
) -> list[EncounterDiagnosis]:
    """按顺序保存诊断：第一条主诊断，其余其他诊断。"""
    encounter = db.get(Encounter, encounter_id)
    if not encounter:
        raise ValueError("就诊记录不存在")
    if encounter.status in ("closed", "abandoned"):
        raise EncounterClosedError("就诊已收费，不能再修改诊断")
    record = get_medical_record(db, encounter_id)
    if record and record.signed_at:
        raise ValueError("病历已签名，不能修改诊断")
    if len(items) > 20:
        raise ValueError("诊断最多 20 条")
    normalized = []
    seen = set()
    for index, item in enumerate(items):
        name = (item.diagnosis or "").strip()
        if not name:
            raise ValueError("诊断名称不能为空")
        code, name = _resolve_diagnosis(db, item.diagnosis_code, name)
        key = (code, name)
        if key in seen:
            raise ValueError(f"诊断重复：{name}")
        seen.add(key)
        normalized.append(
            {
                "diagnosis_code": code,
                "diagnosis": name,
                "diagnosis_type": "primary" if index == 0 else "secondary",
                "diagnosis_stage": getattr(item, "diagnosis_stage", "outpatient"),
                "diagnosis_phase": getattr(item, "diagnosis_phase", "initial"),
                "diagnosis_certainty": getattr(item, "diagnosis_certainty", "confirmed"),
                "sort_no": index,
                "note": (item.note or "").strip(),
            }
        )

    (
        db.query(EncounterDiagnosis)
        .filter(EncounterDiagnosis.encounter_id == encounter_id)
        .delete(synchronize_session=False)
    )
    rows = []
    for data in normalized:
        row = EncounterDiagnosis(encounter_id=encounter_id, **data)
        db.add(row)
        rows.append(row)
    if normalized:
        encounter.diagnosis_code = normalized[0]["diagnosis_code"]
        encounter.diagnosis = normalized[0]["diagnosis"]
    else:
        encounter.diagnosis_code = ""
        encounter.diagnosis = ""
    db.commit()
    for row in rows:
        db.refresh(row)
    return rows


def update_diagnosis(
    db: Session, encounter_id: int, diagnosis_code: str, diagnosis: str
) -> Encounter:
    """兼容旧接口：更新主诊断，保留其他诊断。"""
    encounter = db.get(Encounter, encounter_id)
    if not encounter:
        raise ValueError("就诊记录不存在")
    if encounter.status in ("closed", "abandoned"):
        raise EncounterClosedError("就诊已收费，不能再修改诊断")
    code, name = _resolve_diagnosis(db, diagnosis_code, diagnosis)
    primary = (
        db.query(EncounterDiagnosis)
        .filter(EncounterDiagnosis.encounter_id == encounter_id)
        .order_by(EncounterDiagnosis.sort_no, EncounterDiagnosis.id)
        .first()
    )
    if primary:
        primary.diagnosis_code = code
        primary.diagnosis = name
        primary.diagnosis_type = "primary"
    else:
        db.add(
            EncounterDiagnosis(
                encounter_id=encounter.id,
                diagnosis_code=code,
                diagnosis=name,
                diagnosis_type="primary",
                sort_no=0,
            )
        )
    encounter.diagnosis_code = code
    encounter.diagnosis = name
    db.commit()
    db.refresh(encounter)
    return encounter


MAX_WESTERN_DRUGS = 5


def _next_prescription_no(db: Session, encounter_id: int) -> str:
    count = db.query(func.count(Prescription.id)).filter(
        Prescription.encounter_id == encounter_id
    ).scalar() or 0
    return f"RX{datetime.now():%Y%m%d}{encounter_id:06d}{count + 1:02d}"


def get_or_create_western_prescription(
    db: Session, encounter_id: int, operator: str = "", rx_type: str = "western"
) -> Prescription:
    """复用待审处方；已批准/已发药的处方不能继续追加，必须新开一张。"""
    prescription = (
        db.query(Prescription)
        .filter(
            Prescription.encounter_id == encounter_id,
            Prescription.type == rx_type,
            Prescription.status.in_(("pending_review", "draft")),
        )
        .order_by(Prescription.id.desc())
        .first()
    )
    if prescription:
        return prescription
    if not getattr(settings, "REQUIRE_PRESCRIPTION_REVIEW", True):
        # 兼容“审方关闭”的部署：继续在同一张已批准处方上追加
        prescription = (
            db.query(Prescription)
            .filter(
                Prescription.encounter_id == encounter_id,
                Prescription.type == rx_type,
                Prescription.status == "approved",
            )
            .order_by(Prescription.id.desc())
            .first()
        )
        if prescription:
            return prescription
    prescription = Prescription(
        encounter_id=encounter_id,
        prescription_no=_next_prescription_no(db, encounter_id),
        type=rx_type,
        status=(
            "pending_review"
            if getattr(settings, "REQUIRE_PRESCRIPTION_REVIEW", True)
            else "approved"
        ),
        prescribed_by=operator,
    )
    db.add(prescription)
    db.flush()
    if prescription.status == "pending_review":
        from app.modules.approval.service import ensure_request

        ensure_request(
            db,
            "prescription",
            prescription.id,
            f"处方审方 {prescription.prescription_no}",
            "pharmacist",
            applicant=operator,
        )
    return prescription


def get_prescription(db: Session, prescription_id: int) -> Prescription | None:
    return db.get(Prescription, prescription_id)


def list_prescription_lines(db: Session, encounter_id: int) -> list[PrescriptionLine]:
    return (
        db.query(PrescriptionLine)
        .join(Prescription, PrescriptionLine.prescription_id == Prescription.id)
        .filter(Prescription.encounter_id == encounter_id)
        .order_by(PrescriptionLine.id)
        .all()
    )


def list_prescription_headers(db: Session, encounter_id: int) -> list[Prescription]:
    return (
        db.query(Prescription)
        .filter(Prescription.encounter_id == encounter_id)
        .order_by(Prescription.id.desc())
        .all()
    )


def _reject_prescription_lines(db: Session, row: Prescription) -> None:
    from app.modules.charges.models import EncounterCharge

    for item in list(row.items):
        charge = (
            db.query(EncounterCharge)
            .filter(
                EncounterCharge.source_type == "prescription",
                EncounterCharge.source_id == item.id,
            )
            .first()
        )
        if charge and charge.status == "paid":
            raise ValueError("处方已收费，不能直接驳回；请先退费")
        if charge:
            db.delete(charge)
        db.delete(item)


def finalize_prescription_approval(
    db: Session,
    row: Prescription,
    approved: bool,
    reviewer: str,
    note: str,
) -> Prescription:
    if not approved:
        _reject_prescription_lines(db, row)
        row.status = "rejected"
    else:
        row.status = "approved"
    row.reviewed_by = reviewer
    row.reviewed_at = datetime.now()
    row.review_note = (note or "").strip()
    row.updated_at = datetime.now()
    db.flush()
    return row


def review_prescription(
    db: Session,
    encounter_id: int,
    prescription_id: int,
    approve: bool,
    note: str,
    reviewer: str,
) -> Prescription:
    row = (
        db.query(Prescription)
        .filter(
            Prescription.id == prescription_id,
            Prescription.encounter_id == encounter_id,
        )
        .first()
    )
    if not row:
        raise ValueError("处方不存在")
    if row.status != "pending_review":
        raise ValueError("仅待审处方可以审核")
    if not approve and not (note or "").strip():
        raise ValueError("驳回必须填写原因")

    from app.modules.approval.service import advance_request, record_event

    result = advance_request(
        db,
        "prescription",
        row.id,
        "approve" if approve else "reject",
        reviewer,
        note,
    )
    if result in ("pending", "transferred"):
        row.review_note = (note or "").strip()
        row.updated_at = datetime.now()
        db.commit()
        db.refresh(row)
        return row
    if result == "missing":
        result = "approved" if approve else "rejected"

    finalize_prescription_approval(
        db, row, result == "approved", reviewer, note
    )
    record_event(
        db,
        "prescription",
        row.id,
        "approve" if result == "approved" else "reject",
        reviewer,
        row.review_note,
        step="pharmacist_review",
    )
    if result == "approved":
        try:
            from app.modules.nursing.service import sync_orders

            sync_orders(db, encounter_id)
        except Exception:
            pass
    db.refresh(row)
    return row


def upload_prescription_insurance(
    db: Session, encounter_id: int, prescription_id: int, operator: str = ""
) -> Prescription:
    """按处方头逐张上传医保（当前为状态/审计接口，真实报文由适配器替换）。"""
    row = (
        db.query(Prescription)
        .filter(
            Prescription.id == prescription_id,
            Prescription.encounter_id == encounter_id,
        )
        .first()
    )
    if not row:
        raise ValueError("处方不存在")
    if row.status != "approved":
        raise ValueError("仅审方通过的处方可以上传医保")
    from app.modules.insurance.prescription_upload import upload_prescription

    result = upload_prescription(row, list(row.items), db)
    # 未配置真实地址时只记录本地模拟，不能冒充医保已接收
    row.insurance_upload_status = "uploaded" if result.get("mode") == "http" else "local"
    row.insurance_uploaded_at = datetime.now()
    row.updated_at = datetime.now()
    db.flush()
    from app.modules.approval.service import record_event

    record_event(
        db,
        "prescription",
        row.id,
        "insurance_upload",
        operator,
        "按处方头上传医保",
        step="insurance",
    )
    db.refresh(row)
    return row


def prescription_center(db: Session, encounter_id: int) -> dict:
    """统一处方中心：西药/中成药处方头、中药饮片、治疗单的只读聚合。"""
    from app.modules.tcm.models import TcmPrescription
    from app.modules.treatment.models import TreatmentOrder

    encounter = get_encounter(db, encounter_id)
    if not encounter:
        raise ValueError("就诊记录不存在")
    headers = list_prescription_headers(db, encounter_id)
    from collections import Counter

    line_counts = Counter(
        line.prescription_id for line in list_prescription_lines(db, encounter_id)
    )
    western = []
    for row in headers:
        if row.type == "tcm_herb":
            continue
        western.append(
            {
                "id": row.id,
                "prescription_no": row.prescription_no,
                "type": row.type,
                "status": row.status,
                "prescribed_by": row.prescribed_by,
                "reviewed_by": row.reviewed_by,
                "review_note": row.review_note,
                "item_count": line_counts.get(row.id) or len(row.items),
                "line_count": line_counts.get(row.id, 0),
                "insurance_upload_status": row.insurance_upload_status,
                "created_at": row.created_at,
            }
        )
    tcm = [
        {
            "id": row.id,
            "prescription_no": row.prescription_no,
            "formula_name": row.formula_name,
            "status": row.status,
            "packs": row.packs,
            "item_count": line_counts.get(row.prescription_id) or len(row.items),
            "line_count": line_counts.get(row.prescription_id, 0),
            "prescription_id": row.prescription_id,
        }
        for row in db.query(TcmPrescription)
        .filter(TcmPrescription.encounter_id == encounter_id)
        .order_by(TcmPrescription.id)
        .all()
    ]
    treatments = [
        {
            "id": row.id,
            "item_name": row.item_name,
            "status": row.status,
            "quantity": row.quantity,
        }
        for row in db.query(TreatmentOrder)
        .filter(TreatmentOrder.encounter_id == encounter_id)
        .order_by(TreatmentOrder.id)
        .all()
    ]
    return {
        "encounter_id": encounter_id,
        "western": western,
        "tcm": tcm,
        "treatments": treatments,
    }


def list_pending_prescription_reviews(db: Session) -> list[dict]:
    """药师审方工作台：待审处方 + 患者/医生/明细数。"""
    from app.modules.patient.models import Patient
    from app.modules.registration.models import Registration
    from app.modules.staff.models import Doctor

    rows = (
        db.query(Prescription, Encounter, Registration, Patient, Doctor)
        .join(Encounter, Prescription.encounter_id == Encounter.id)
        .join(Registration, Encounter.registration_id == Registration.id)
        .join(Patient, Registration.patient_id == Patient.id)
        .join(Doctor, Registration.doctor_id == Doctor.id)
        .filter(
            Prescription.status == "pending_review",
            Prescription.type != "tcm_herb",
        )
        .order_by(Prescription.id)
        .all()
    )
    result = []
    for rx, encounter, registration, patient, doctor in rows:
        result.append(
            {
                "id": rx.id,
                "encounter_id": encounter.id,
                "prescription_no": rx.prescription_no,
                "type": rx.type,
                "status": rx.status,
                "prescribed_by": rx.prescribed_by,
                "created_at": rx.created_at,
                "patient_id": patient.id,
                "patient_no": patient.patient_no,
                "patient_name": patient.name,
                "gender": patient.gender,
                "age": patient.age,
                "doctor_name": doctor.name,
                "item_count": len(rx.items),
            }
        )
    return result


def add_prescription_item(
    db: Session,
    encounter_id: int,
    data: PrescriptionItemCreate,
    operator: str = "",
    commit: bool = True,
) -> PrescriptionItem:
    """给就诊添加一条处方明细：单价取药品基准价（快照进明细）。

    已关闭（已收费）的就诊不能再开处方。
    """
    encounter = db.get(Encounter, encounter_id)
    if not encounter:
        raise ValueError("就诊记录不存在")

    if encounter.status in ("closed", "abandoned"):
        raise EncounterClosedError("就诊已收费，不能再开处方")
    record = get_medical_record(db, encounter_id)
    if record and record.signed_at:
        raise ValueError("病历已签名，不能再开处方")

    drug = get_drug(db, data.drug_id)
    if not drug:
        raise ValueError("药品不存在")

    controlled = getattr(drug, "controlled_level", "") or ""
    rx_type = "narcotic" if controlled in ("narcotic", "psychotropic1") else "western"
    if rx_type == "narcotic":
        from app.modules.auth.service import get_user_by_username

        prescriber = get_user_by_username(db, operator) if operator else None
        if prescriber and prescriber.role != "admin" and not getattr(prescriber, "narcotic_right", False):
            raise PrescriptionRuleError("当前医师无麻醉/第一类精神药品处方权")

    # 《处方管理办法》：每张西药/中成药处方不得超过 5 种药品（按处方头计数）
    prescription = get_or_create_western_prescription(db, encounter_id, operator, rx_type)
    current_count = (
        db.query(PrescriptionItem)
        .filter(PrescriptionItem.prescription_id == prescription.id)
        .count()
    )
    if current_count >= MAX_WESTERN_DRUGS:
        raise PrescriptionRuleError(
            f"每张西药/中成药处方不得超过 {MAX_WESTERN_DRUGS} 种药品"
        )

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

    # 用药安全：成分重复 / 已维护的相互作用规则（规则为空时不拦截）
    from app.modules.drug.models import DrugInteraction

    existing_items = (
        db.query(PrescriptionItem)
        .filter(PrescriptionItem.encounter_id == encounter_id)
        .all()
    )
    for row in existing_items:
        other = get_drug(db, row.drug_id)
        if not other:
            continue
        if (
            drug.ingredient.strip()
            and other.ingredient.strip()
            and drug.ingredient.strip() == other.ingredient.strip()
        ):
            raise PrescriptionRuleError(
                f"成分重复：{drug.name} 与 {other.name} 均含「{drug.ingredient}」"
            )
        rule = (
            db.query(DrugInteraction)
            .filter(
                DrugInteraction.active.is_(True),
                (
                    ((DrugInteraction.drug_a_id == drug.id) & (DrugInteraction.drug_b_id == other.id))
                    | ((DrugInteraction.drug_a_id == other.id) & (DrugInteraction.drug_b_id == drug.id))
                ),
            )
            .first()
        )
        if rule and rule.severity == "block":
            raise PrescriptionRuleError(
                f"相互作用禁止同方：{drug.name} + {other.name}；{rule.note or '请核对'}"
            )

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

    # 医保事前提醒：医保总开关关闭时不应调用 Mock 平台，否则自费药可能被误判禁止
    warning = None
    if settings.INSURANCE_ENABLED:
        from app.modules.insurance.audit import record_check

        try:
            review = check_prescription(
                diagnosis=encounter.diagnosis,
                drug_name=drug.name,
                quantity=data.quantity,
                ratio=insurance_ratio,
            )
        except InsuranceUnavailable:
            warning = "医保服务不可用，已按自费放行"
            record_check(
                db,
                encounter_id=encounter_id,
                drug_name=drug.name,
                quantity=data.quantity,
                ratio=insurance_ratio,
                result="unavailable",
                message=warning,
                operator=operator,
            )
        else:
            if review["result"] == "forbid":
                record_check(
                    db,
                    encounter_id=encounter_id,
                    drug_name=drug.name,
                    quantity=data.quantity,
                    ratio=insurance_ratio,
                    result="forbid",
                    message=review["message"],
                    operator=operator,
                )
                if insurance_ratio <= 0 and catalog_warning:
                    # 目录内丙类/目录外（已对码）：允许自费开方，不拦截
                    warning = catalog_warning
                else:
                    raise InsuranceForbiddenError(review["message"])
            else:
                warning = review["message"] if review["result"] == "warn" else None
                record_check(
                    db,
                    encounter_id=encounter_id,
                    drug_name=drug.name,
                    quantity=data.quantity,
                    ratio=insurance_ratio,
                    result=review["result"],
                    message=review["message"],
                    operator=operator,
                )

    warnings: list[str] = []
    for text in (catalog_warning, warning):
        if text and text not in warnings:
            warnings.append(text)
    item = PrescriptionItem(
        encounter_id=encounter_id,
        prescription_id=prescription.id,
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
    db.add(
        PrescriptionLine(
            prescription_id=prescription.id,
            kind="drug",
            drug_id=drug.id,
            source_item_id=item.id,
            name=drug.name,
            spec=drug.spec,
            quantity=data.quantity,
            unit=drug.unit,
            dosage=data.dosage,
            frequency=data.frequency,
            route=data.route,
            days=data.days,
            unit_price=drug.base_price,
            amount=round(data.quantity * drug.base_price, 2),
        )
    )

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




def update_prescription_item(
    db: Session,
    encounter_id: int,
    item_id: int,
    data,
    operator: str = "",
) -> PrescriptionItem:
    encounter = db.get(Encounter, encounter_id)
    if not encounter:
        raise ValueError("就诊记录不存在")
    if encounter.status in ("closed", "abandoned"):
        raise EncounterClosedError("就诊已收费，不能修改处方")
    item = (
        db.query(PrescriptionItem)
        .filter(
            PrescriptionItem.id == item_id,
            PrescriptionItem.encounter_id == encounter_id,
        )
        .first()
    )
    if not item:
        raise ValueError("处方明细不存在")
    if item.prescription and item.prescription.status != "pending_review":
        raise ValueError("只有待审处方可以修改用法；已审方请新开处方")
    from app.modules.charges.models import EncounterCharge

    charge = (
        db.query(EncounterCharge)
        .filter(
            EncounterCharge.source_type == "prescription",
            EncounterCharge.source_id == item.id,
        )
        .first()
    )
    if charge and charge.status == "paid":
        raise ValueError("该处方明细已收费，不能修改数量；请先退费")
    if data.quantity is not None:
        item.quantity = data.quantity
        if charge:
            charge.quantity = data.quantity
            charge.amount = round(data.quantity * charge.unit_price, 2)
    item.dosage = data.dosage
    item.frequency = data.frequency
    item.route = data.route
    item.days = data.days
    line = (
        db.query(PrescriptionLine)
        .filter(
            PrescriptionLine.kind == "drug",
            PrescriptionLine.source_item_id == item.id,
        )
        .first()
    )
    if line:
        line.quantity = item.quantity
        line.dosage = item.dosage
        line.frequency = item.frequency
        line.route = item.route
        line.days = item.days
        line.amount = round(item.quantity * item.unit_price, 2)
    db.commit()
    db.refresh(item)
    return item


def delete_prescription_item(db: Session, encounter_id: int, item_id: int) -> None:
    """删除未收费的处方明细，并同步删除未收费的药品费用。"""
    encounter = db.get(Encounter, encounter_id)
    if not encounter:
        raise ValueError("就诊记录不存在")
    if encounter.status in ("closed", "abandoned"):
        raise EncounterClosedError("就诊已收费，不能删除处方")
    item = (
        db.query(PrescriptionItem)
        .filter(
            PrescriptionItem.id == item_id,
            PrescriptionItem.encounter_id == encounter_id,
        )
        .first()
    )
    if not item:
        raise ValueError("处方明细不存在")
    from app.modules.charges.models import EncounterCharge

    charge = (
        db.query(EncounterCharge)
        .filter(
            EncounterCharge.source_type == "prescription",
            EncounterCharge.source_id == item.id,
        )
        .first()
    )
    if charge and charge.status == "paid":
        raise ValueError("该处方已收费，不能直接删除；请先退费")
    if charge:
        db.delete(charge)
    prescription_id = item.prescription_id
    line = (
        db.query(PrescriptionLine)
        .filter(
            PrescriptionLine.kind == "drug",
            PrescriptionLine.source_item_id == item.id,
        )
        .first()
    )
    if line:
        db.delete(line)
    db.delete(item)
    db.flush()
    if prescription_id:
        remaining = (
            db.query(PrescriptionItem)
            .filter(PrescriptionItem.prescription_id == prescription_id)
            .count()
        )
        if remaining == 0:
            header = db.get(Prescription, prescription_id)
            if header:
                db.delete(header)
    db.commit()


def add_prescription_items_batch(
    db: Session,
    encounter_id: int,
    items: list[PrescriptionItemCreate],
    operator: str = "",
) -> list[PrescriptionItem]:
    """批量开方：任一药品失败则整批回滚，避免半张处方和半套费用。"""
    if not items:
        raise ValueError("处方不能为空")
    try:
        created = [
            add_prescription_item(db, encounter_id, data, operator, commit=False)
            for data in items
        ]
        db.commit()
        for row in created:
            db.refresh(row)
        return created
    except Exception:
        db.rollback()
        raise


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


def release_doctor_lock(db: Session, doctor_id: int) -> dict:
    """解除医生当前接诊占用（用于旧数据/异常中断恢复）。"""
    from app.modules.staff.models import Doctor

    doctor = db.get(Doctor, doctor_id)
    if not doctor:
        raise ValueError("医生不存在")
    old = doctor.current_encounter_id
    doctor.current_encounter_id = None
    db.commit()
    return {"doctor_id": doctor_id, "released_encounter_id": old}


def complete_encounter_without_charge(
    db: Session, encounter_id: int, waive_pending: bool = False
) -> Encounter:
    """无费用完诊：适用于复诊/看结果，不生成 0 元发票。"""
    encounter = db.get(Encounter, encounter_id)
    if not encounter:
        raise ValueError("就诊记录不存在")
    if encounter.status in ("closed", "abandoned", "cancelled"):
        raise ValueError("该就诊已经结束")
    from app.modules.billing.models import Payment
    from app.modules.charges.models import EncounterCharge

    pending = db.query(EncounterCharge).filter(
        EncounterCharge.encounter_id == encounter_id,
        EncounterCharge.status == "pending",
    ).all()
    if pending and not waive_pending:
        raise ValueError("仍有待收费项目，不能无费用完诊")
    if pending and waive_pending:
        for row in pending:
            row.status = "refunded"
    if db.query(Payment).filter(
        Payment.encounter_id == encounter_id,
        Payment.status.in_(("paid", "partially_refunded")),
    ).first():
        raise ValueError("该就诊已有收费，不能无费用完诊")
    encounter.status = "closed"
    from app.modules.registration.service import get_registration
    from app.modules.staff.models import Doctor

    registration = get_registration(db, encounter.registration_id)
    doctor = db.get(Doctor, registration.doctor_id) if registration else None
    if doctor and doctor.current_encounter_id == encounter.id:
        doctor.current_encounter_id = None
    db.commit()
    db.refresh(encounter)
    return encounter


def abandon_encounter(db: Session, encounter_id: int, reason: str = "") -> Encounter:
    """患者中途放弃：关闭本次接诊，作废未收费项目；不生成收费单。"""
    encounter = db.get(Encounter, encounter_id)
    if not encounter:
        raise ValueError("就诊记录不存在")
    if encounter.status in ("closed", "abandoned"):
        raise ValueError("就诊已收费，不能放弃；请走退费流程")
    if encounter.status in ("abandoned", "cancelled"):
        raise ValueError("该就诊已经结束")
    from app.modules.billing.models import Payment
    from app.modules.charges.models import EncounterCharge
    from app.modules.lis.models import LabRequest
    from app.modules.pacs.models import ImagingRequest
    from app.modules.treatment.models import TreatmentOrder

    if db.query(Payment).filter(
        Payment.encounter_id == encounter_id,
        Payment.status.in_(("paid", "partially_refunded")),
    ).first():
        raise ValueError("该就诊已有有效收费，不能直接放弃；请先退费")
    encounter.status = "abandoned"
    if reason:
        encounter.diagnosis = (encounter.diagnosis or "")[:180]
    for row in db.query(EncounterCharge).filter(
        EncounterCharge.encounter_id == encounter_id,
        EncounterCharge.status == "pending",
    ):
        row.status = "refunded"
    for row in db.query(LabRequest).filter(
        LabRequest.encounter_id == encounter_id,
        LabRequest.status.in_(("pending", "collected", "received", "testing")),
    ):
        row.status = "cancelled"
    for row in db.query(ImagingRequest).filter(
        ImagingRequest.encounter_id == encounter_id,
        ImagingRequest.status == "pending",
    ):
        row.status = "cancelled"
    for row in db.query(TreatmentOrder).filter(
        TreatmentOrder.encounter_id == encounter_id,
        TreatmentOrder.status == "pending",
    ):
        row.status = "cancelled"
    from app.modules.encounter.models import Prescription

    for row in db.query(Prescription).filter(
        Prescription.encounter_id == encounter_id,
        Prescription.status.in_(("pending_review", "draft")),
    ):
        row.status = "cancelled"
    from app.modules.registration.service import get_registration
    from app.modules.staff.models import Doctor

    registration = get_registration(db, encounter.registration_id)
    doctor = db.get(Doctor, registration.doctor_id) if registration else None
    if doctor and doctor.current_encounter_id == encounter.id:
        doctor.current_encounter_id = None
    db.commit()
    db.refresh(encounter)
    return encounter


def close_encounter(db: Session, encounter: Encounter) -> None:
    """把就诊状态改为 closed（只改内存，由调用方统一 commit）。"""
    encounter.status = "closed"
    from app.modules.registration.service import get_registration
    from app.modules.staff.models import Doctor

    registration = get_registration(db, encounter.registration_id)
    doctor = db.get(Doctor, registration.doctor_id) if registration else None
    if doctor and doctor.current_encounter_id == encounter.id:
        doctor.current_encounter_id = None


def list_dispensable_prescription_items(
    db: Session, encounter_id: int
) -> list[PrescriptionItem]:
    """只返回已审方通过的处方明细；拒绝/待审处方不进入发药。"""
    return (
        db.query(PrescriptionItem)
        .outerjoin(Prescription, PrescriptionItem.prescription_id == Prescription.id)
        .filter(
            PrescriptionItem.encounter_id == encounter_id,
            (Prescription.id.is_(None)) | (Prescription.status == "approved"),
        )
        .order_by(PrescriptionItem.id)
        .all()
    )


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


_RECORD_SNAPSHOT_FIELDS = (
    "chief_complaint",
    "present_illness",
    "past_history",
    "personal_history",
    "marital_history",
    "family_history",
    "physical_exam",
    "auxiliary_exam",
    "treatment_advice",
)


def _record_snapshot(record: MedicalRecord | None) -> str:
    if not record:
        return ""
    return json.dumps(
        {key: getattr(record, key, "") or "" for key in _RECORD_SNAPSHOT_FIELDS},
        ensure_ascii=False,
    )


def _add_record_version(
    db: Session,
    record: MedicalRecord,
    *,
    action: str,
    changed_by: str,
    before: str = "",
) -> None:
    version = (
        db.query(func.count(MedicalRecordVersion.id))
        .filter(MedicalRecordVersion.record_id == record.id)
        .scalar()
        or 0
    ) + 1
    db.add(
        MedicalRecordVersion(
            record_id=record.id,
            version=version,
            action=action,
            changed_by=changed_by,
            before_json=before,
            after_json=_record_snapshot(record),
        )
    )


def list_medical_record_versions(db: Session, encounter_id: int) -> list[MedicalRecordVersion]:
    record = get_medical_record(db, encounter_id)
    if not record:
        raise ValueError("病历不存在")
    return (
        db.query(MedicalRecordVersion)
        .filter(MedicalRecordVersion.record_id == record.id)
        .order_by(MedicalRecordVersion.version)
        .all()
    )


def create_medical_record(
    db: Session, encounter_id: int, data: MedicalRecordCreate, written_by: str = ""
) -> MedicalRecord:
    """书写门诊结构化病历：一次就诊一份，收费关闭后不可书写。"""
    encounter = get_encounter(db, encounter_id)
    if not encounter:
        raise ValueError("就诊记录不存在")
    if encounter.status in ("closed", "abandoned"):
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
    db.flush()
    _add_record_version(db, record, action="create", changed_by=written_by)
    db.commit()
    db.refresh(record)
    return record


def get_medical_record(db: Session, encounter_id: int) -> MedicalRecord | None:
    return (
        db.query(MedicalRecord)
        .filter(MedicalRecord.encounter_id == encounter_id)
        .first()
    )


def unlock_medical_record_for_refund(
    db: Session, encounter_id: int, operator: str = ""
) -> None:
    """全额退费后解锁病历：保留签名前快照和版本，允许医生修订。"""
    record = get_medical_record(db, encounter_id)
    if not record or not record.signed_at:
        return
    before = _record_snapshot(record)
    record.signed_at = None
    record.signed_by = ""
    _add_record_version(
        db,
        record,
        action="unlock_refund",
        changed_by=operator,
        before=before,
    )


def update_medical_record(
    db: Session, encounter_id: int, data: MedicalRecordUpdate, operator: str = ""
) -> MedicalRecord:
    """修改病历：就诊关闭或病历已签名后不可修改。"""
    encounter = get_encounter(db, encounter_id)
    if not encounter:
        raise ValueError("就诊记录不存在")
    if encounter.status in ("closed", "abandoned"):
        raise ValueError("就诊已关闭，不能修改病历")

    record = get_medical_record(db, encounter_id)
    if not record:
        raise ValueError("该就诊还没有病历")
    if record.signed_at:
        raise ValueError("病历已签名，不能修改")

    before = _record_snapshot(record)
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(record, field, value)
    record.updated_at = datetime.now()
    db.flush()
    _add_record_version(
        db, record, action="update", changed_by=operator, before=before
    )
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

    before = _record_snapshot(record)
    record.signed_by = signed_by
    record.signed_at = datetime.now()
    _add_record_version(db, record, action="sign", changed_by=signed_by, before=before)
    db.commit()
    db.refresh(record)
    return record


def request_record_revision(
    db: Session, encounter_id: int, reason: str, requested_by: str = ""
) -> MedicalRecordRevision:
    record = get_medical_record(db, encounter_id)
    if not record:
        raise ValueError("病历不存在")
    if not record.signed_at:
        raise ValueError("病历未签名，无需申请修订")
    reason = (reason or "").strip()
    if not reason:
        raise ValueError("修订理由不能为空")
    pending = (
        db.query(MedicalRecordRevision)
        .filter(
            MedicalRecordRevision.encounter_id == encounter_id,
            MedicalRecordRevision.status == "pending",
        )
        .first()
    )
    if pending:
        raise ValueError("该病历已有待审批修订申请")
    row = MedicalRecordRevision(
        encounter_id=encounter_id,
        reason=reason,
        status="pending",
        requested_by=requested_by,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def list_record_revisions(
    db: Session, status: str | None = None
) -> list[MedicalRecordRevision]:
    query = db.query(MedicalRecordRevision)
    if status:
        query = query.filter(MedicalRecordRevision.status == status)
    return query.order_by(MedicalRecordRevision.id.desc()).all()


def review_record_revision(
    db: Session, revision_id: int, approve: bool, reviewer: str, note: str = ""
) -> MedicalRecordRevision:
    row = db.get(MedicalRecordRevision, revision_id)
    if not row:
        raise ValueError("修订申请不存在")
    if row.status != "pending":
        raise ValueError("该修订申请已处理")
    if not approve and not (note or "").strip():
        raise ValueError("驳回必须填写原因")
    claimed = (
        db.query(MedicalRecordRevision)
        .filter(
            MedicalRecordRevision.id == revision_id,
            MedicalRecordRevision.status == "pending",
        )
        .update({MedicalRecordRevision.status: "reviewing"}, synchronize_session=False)
    )
    if claimed != 1:
        db.rollback()
        raise ValueError("该修订申请正在处理")
    row.status = "approved" if approve else "rejected"
    row.reviewed_by = reviewer
    row.review_note = (note or "").strip()
    row.reviewed_at = datetime.now()
    if approve:
        record = get_medical_record(db, row.encounter_id)
        if not record:
            db.rollback()
            raise ValueError("病历不存在")
        before = _record_snapshot(record)
        record.signed_at = None
        record.signed_by = ""
        _add_record_version(
            db,
            record,
            action="unlock_revision",
            changed_by=reviewer,
            before=before,
        )
    db.commit()
    db.refresh(row)
    return row


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

def worklist(db: Session, doctor_id: int | None = None) -> list[dict]:
    """医生门诊队列：待接诊 + 今日已接诊，带费用预览。"""
    from datetime import date

    from app.modules.charges.service import list_charges
    from app.modules.patient.models import Patient
    from app.modules.registration.models import Registration
    from app.modules.staff.models import Doctor
    from app.modules.triage.models import TriageTicket

    query = (
        db.query(Registration, Patient, Doctor)
        .join(Patient, Registration.patient_id == Patient.id)
        .join(Doctor, Registration.doctor_id == Doctor.id)
    )
    if doctor_id:
        query = query.filter(Registration.doctor_id == doctor_id)
    rows = query.order_by(Registration.id.desc()).all()
    # 治疗中/待治疗状态是就诊状态的补充：医生挂起后患者可能正在输液
    from app.modules.treatment.models import TreatmentOrder
    from app.modules.treatment_room.models import TreatmentRoomCase

    case_by_encounter = {
        row.encounter_id: row
        for row in db.query(TreatmentRoomCase)
        .filter(
            TreatmentRoomCase.encounter_id.isnot(None),
            TreatmentRoomCase.status.in_(("waiting", "in_progress")),
        )
        .all()
    }
    pending_order_encounters = {
        row.encounter_id
        for row in db.query(TreatmentOrder)
        .filter(TreatmentOrder.status == "pending")
        .all()
    }
    result = []
    for registration, patient, doctor in rows:
        encounter = (
            db.query(Encounter)
            .filter(Encounter.registration_id == registration.id)
            .order_by(Encounter.id.desc())
            .first()
        )
        if encounter is None and registration.status != "registered":
            continue
        cross_day = bool(encounter and encounter.created_at.date() != date.today())
        if encounter is not None:
            # 已收费的只保留今天；未完成的跨日保留 14 天，便于看结果/继续接诊
            if encounter.status == "closed" and cross_day:
                continue
            if encounter.status in ("open", "paused") and encounter.created_at < datetime.now() - timedelta(days=14):
                continue
        charges = list_charges(db, encounter.id) if encounter else []
        total = round(sum(row.amount for row in charges), 2)
        pending = round(sum(row.amount for row in charges if row.status == "pending"), 2)
        ticket = (
            db.query(TriageTicket)
            .filter(TriageTicket.registration_id == registration.id)
            .first()
        )
        case = case_by_encounter.get(encounter.id) if encounter else None
        if case and case.status == "in_progress":
            treatment_status = "in_progress"
        elif case or (encounter and encounter.id in pending_order_encounters):
            treatment_status = "waiting"
        else:
            treatment_status = ""
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
                "allergy_status": patient.allergy_status,
                "special_history": patient.special_history,
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
                "visit_type": registration.visit_type or "initial",
                "original_registration_id": registration.original_registration_id,
                "encounter_id": encounter.id if encounter else None,
                "encounter_status": encounter.status if encounter else "",
                "treatment_status": treatment_status,
                "treatment_case_id": case.id if case else None,
                "encounter_date": encounter.created_at.strftime("%Y-%m-%d") if encounter else "",
                "cross_day": cross_day,
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
        "patient_no": patient.patient_no if patient else "",
        "patient_name": patient.name if patient else "",
        "gender": patient.gender if patient else "",
        "age": patient.age if patient else None,
        "allergy_label": patient.allergy_label if patient else "",
        "special_history": patient.special_history if patient else "",
        "phone": patient.phone if patient else "",
        "doctor_name": doctor.name if doctor else "",
        "diagnosis": encounter.diagnosis,
        "diagnosis_code": encounter.diagnosis_code,
        "diagnoses": [
            {
                "id": row.id,
                "diagnosis_code": row.diagnosis_code,
                "diagnosis": row.diagnosis,
                "diagnosis_type": row.diagnosis_type,
                "sort_no": row.sort_no,
                "note": row.note,
            }
            for row in list_encounter_diagnoses(db, encounter.id)
        ],
        "visit_type": encounter.visit_type or "initial",
        "original_encounter_id": encounter.original_encounter_id,
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



def pause_encounter(db: Session, encounter_id: int) -> Encounter:
    """显式挂起当前就诊，允许医生先处理其他患者。"""
    encounter = db.get(Encounter, encounter_id)
    if not encounter:
        raise ValueError("就诊记录不存在")
    if encounter.status in ("closed", "abandoned"):
        raise ValueError("就诊已收费关闭，不能挂起")
    encounter.status = "paused"
    db.commit()
    db.refresh(encounter)
    return encounter


def return_encounter(
    db: Session,
    encounter_id: int,
    diagnosis: str = "",
    diagnosis_code: str = "",
) -> Encounter:
    """已收费患者回诊：同一挂号下新建回诊就诊，不重新挂号。"""
    original = db.get(Encounter, encounter_id)
    if not original:
        raise ValueError("就诊记录不存在")
    if original.status != "closed":
        raise ValueError("只有已收费关闭的就诊可以回诊")
    registration = get_registration(db, original.registration_id)
    if not registration:
        raise ValueError("挂号记录不存在")

    # 同一挂号如果已有进行中/挂起的回诊，直接返回，避免重复点出多条
    current = (
        db.query(Encounter)
        .filter(
            Encounter.registration_id == registration.id,
            Encounter.status.in_(("open", "paused")),
            Encounter.id != original.id,
        )
        .order_by(Encounter.id.desc())
        .first()
    )
    if current:
        return current

    from app.modules.staff.models import Doctor

    doctor = db.get(Doctor, registration.doctor_id)
    if doctor and doctor.current_encounter_id:
        active = db.get(Encounter, doctor.current_encounter_id)
        if active and active.status == "open" and active.id != original.id:
            raise ValueError("当前患者尚未完成诊治，请先完成或挂起当前患者，再回诊")

    encounter = Encounter(
        registration_id=registration.id,
        diagnosis=diagnosis,
        diagnosis_code=diagnosis_code,
        status="open",
        visit_type="follow_up",
        original_encounter_id=original.id,
    )
    encounter.diagnosis_code, encounter.diagnosis = _resolve_diagnosis(
        db, diagnosis_code, diagnosis
    )
    db.add(encounter)
    db.flush()
    if encounter.diagnosis:
        db.add(
            EncounterDiagnosis(
                encounter_id=encounter.id,
                diagnosis_code=encounter.diagnosis_code,
                diagnosis=encounter.diagnosis,
                diagnosis_type="primary",
                sort_no=0,
            )
        )
    mark_registration_visited(db, registration)
    if doctor:
        doctor.current_encounter_id = encounter.id
    # 回诊不自动收挂号费/诊疗费；医生实际开药/开治疗时再产生费用
    db.commit()
    db.refresh(encounter)
    return encounter


def resume_encounter(db: Session, encounter_id: int) -> Encounter:
    """恢复挂起就诊；同一医生有未完成的其他就诊时禁止恢复。"""
    encounter = db.get(Encounter, encounter_id)
    if not encounter:
        raise ValueError("就诊记录不存在")
    if encounter.status in ("closed", "abandoned"):
        raise ValueError("就诊已收费/已放弃关闭，不能恢复")
    from app.modules.registration.service import get_registration
    from app.modules.staff.models import Doctor

    registration = get_registration(db, encounter.registration_id)
    doctor = db.get(Doctor, registration.doctor_id) if registration else None
    if doctor and doctor.current_encounter_id and doctor.current_encounter_id != encounter.id:
        current = db.get(Encounter, doctor.current_encounter_id)
        if current and current.status == "open":
            raise ValueError("请先完成或挂起当前患者，再恢复该患者")
    encounter.status = "open"
    if doctor:
        doctor.current_encounter_id = encounter.id
    db.commit()
    db.refresh(encounter)
    return encounter


def record_adverse_reaction(
    db: Session, encounter_id: int, data, operator: str = ""
) -> AdverseReaction:
    """记录药物反应，默认挂起就诊并停止未完成的护理执行单。"""
    encounter = db.get(Encounter, encounter_id)
    if not encounter:
        raise ValueError("就诊记录不存在")
    row = AdverseReaction(
        encounter_id=encounter_id,
        drug_name=data.drug_name.strip(),
        reaction=data.reaction.strip(),
        severity=data.severity,
        action_taken=data.action_taken.strip(),
        reported_by=operator,
    )
    db.add(row)
    if data.pause_encounter:
        encounter.status = "paused"
        from app.modules.nursing.models import NursingOrder

        orders = (
            db.query(NursingOrder)
            .filter(
                NursingOrder.encounter_id == encounter_id,
                NursingOrder.status.in_(["pending", "prepared", "executing"]),
            )
            .all()
        )
        for order in orders:
            order.status = "stopped"
            order.note = (order.note + "；药物反应停药").strip("；")
    db.commit()
    db.refresh(row)
    return row


def list_adverse_reactions(db: Session, encounter_id: int) -> list[AdverseReaction]:
    return (
        db.query(AdverseReaction)
        .filter(AdverseReaction.encounter_id == encounter_id)
        .order_by(AdverseReaction.id.desc())
        .all()
    )
