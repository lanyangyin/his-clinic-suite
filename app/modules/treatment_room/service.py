"""治疗室：清创/换药/小处置的排队、知情同意、处置记录与计费。"""
from datetime import date, datetime, timedelta
import json

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.modules.charges.models import ChargeItem, EncounterCharge
from app.modules.charges.service import add_charge
from app.modules.encounter.service import get_encounter
from app.modules.materials.models import MaterialItem, MaterialStock
from app.modules.stock_ledger.service import record_material
from app.modules.patient.models import Patient
from app.modules.patient.service import get_patient

from .models import (
    TreatmentFollowUp,
    TreatmentRoom,
    TreatmentRoomCase,
    TreatmentTemplateConfig,
    TreatmentTemplateMaterial,
)
from .schemas import (
    CaseCreate,
    CompleteRequest,
    FollowUpComplete,
    FollowUpCreate,
    RoomCreate,
    StartRequest,
    TemplateConfigUpdate,
)
from .templates import TEMPLATES
from app.modules.procedure_materials.models import ProcedureMaterial


def create_room(db: Session, data: RoomCreate) -> TreatmentRoom:
    if db.query(TreatmentRoom).filter(TreatmentRoom.code == data.code).first():
        raise ValueError("治疗室编码已存在")
    row = TreatmentRoom(**data.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def list_rooms(db: Session) -> list[TreatmentRoom]:
    return db.query(TreatmentRoom).order_by(TreatmentRoom.code).all()


def list_templates(db: Session) -> list[dict]:
    configs = {
        row.template_code: row
        for row in db.query(TreatmentTemplateConfig).all()
    }
    rows = []
    for template in TEMPLATES:
        config = configs.get(template["code"])
        charge_item = db.get(ChargeItem, config.charge_item_id) if config and config.charge_item_id else None
        kit = []
        for line in (config.materials if config else []):
            material = db.get(MaterialItem, line.material_id)
            kit.append(
                {
                    "material_id": line.material_id,
                    "material_name": material.name if material else "",
                    "quantity": line.quantity,
                    "warehouse": line.warehouse,
                }
            )
        first = kit[0] if kit else {}
        rows.append(
            {
                **template,
                "configured": bool(config and config.active),
                "charge_item_id": config.charge_item_id if config else None,
                "charge_item_name": charge_item.name if charge_item else "",
                "price": config.price if config else 0,
                "material_id": first.get("material_id"),
                "material_name": first.get("material_name", ""),
                "material_quantity": first.get("quantity", 1),
                "warehouse": first.get("warehouse", "总库"),
                "materials": kit,
            }
        )
    return rows


def set_template_config(db: Session, template_code: str, data: TemplateConfigUpdate) -> TreatmentTemplateConfig:
    if template_code not in {row["code"] for row in TEMPLATES}:
        raise ValueError("处置模板不存在")
    if data.charge_item_id is not None and not db.get(ChargeItem, data.charge_item_id):
        raise ValueError("收费项目不存在")
    lines = list(data.materials)
    if not lines and data.material_id is not None:
        lines = [
            {
                "material_id": data.material_id,
                "quantity": data.material_quantity,
                "warehouse": data.warehouse or "总库",
            }
        ]
    for line in lines:
        material_id = line.material_id if hasattr(line, "material_id") else line["material_id"]
        if not db.get(MaterialItem, material_id):
            raise ValueError(f"耗材不存在：{material_id}")
    row = (
        db.query(TreatmentTemplateConfig)
        .filter(TreatmentTemplateConfig.template_code == template_code)
        .first()
    )
    if not row:
        row = TreatmentTemplateConfig(template_code=template_code)
        db.add(row)
        db.flush()
    row.charge_item_id = data.charge_item_id
    row.price = data.price
    row.material_id = None
    row.material_quantity = 1
    row.warehouse = "总库"
    row.active = data.active
    row.updated_at = datetime.now()
    for old in list(row.materials):
        db.delete(old)
    for line in lines:
        material_id = line.material_id if hasattr(line, "material_id") else line["material_id"]
        quantity = line.quantity if hasattr(line, "quantity") else line["quantity"]
        warehouse = line.warehouse if hasattr(line, "warehouse") else line["warehouse"]
        db.add(
            TreatmentTemplateMaterial(
                config_id=row.id,
                material_id=material_id,
                quantity=quantity,
                warehouse=warehouse or "总库",
            )
        )
    db.commit()
    db.refresh(row)
    return row


def list_followups(db: Session, status: str | None = None, due_before: date | None = None) -> list[TreatmentFollowUp]:
    query = db.query(TreatmentFollowUp)
    if status:
        query = query.filter(TreatmentFollowUp.status == status)
    if due_before:
        query = query.filter(TreatmentFollowUp.due_date <= due_before)
    return query.order_by(TreatmentFollowUp.due_date, TreatmentFollowUp.id).all()


def create_followup(db: Session, data: FollowUpCreate) -> TreatmentFollowUp:
    if not get_patient(db, data.patient_id):
        raise ValueError("患者不存在")
    if data.case_id is not None and not get_case(db, data.case_id):
        raise ValueError("治疗室病例不存在")
    row = TreatmentFollowUp(**data.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def complete_followup(
    db: Session,
    followup_id: int,
    data: FollowUpComplete | None = None,
    operator: str = "",
) -> TreatmentFollowUp:
    row = db.get(TreatmentFollowUp, followup_id)
    if not row:
        raise ValueError("随访任务不存在")
    if row.status != "pending":
        raise ValueError("该随访任务已结束")
    data = data or FollowUpComplete()
    row.status = "completed"
    row.completed_at = datetime.now()
    row.completed_by = operator
    row.result_note = data.result_note
    row.healing_score = data.healing_score
    if data.next_due_date:
        db.add(
            TreatmentFollowUp(
                case_id=row.case_id,
                patient_id=row.patient_id,
                encounter_id=row.encounter_id,
                due_date=data.next_due_date,
                purpose=data.next_purpose or "换药",
                note=f"{row.purpose}后继续{data.next_purpose or '换药'}",
            )
        )
    db.commit()
    db.refresh(row)
    return row


def cancel_followup(db: Session, followup_id: int) -> TreatmentFollowUp:
    row = db.get(TreatmentFollowUp, followup_id)
    if not row:
        raise ValueError("随访任务不存在")
    if row.status != "pending":
        raise ValueError("该随访任务已结束")
    row.status = "cancelled"
    db.commit()
    db.refresh(row)
    return row


_FOLLOWUP_PLAN = {
    "debridement": (3, "换药"),
    "abscess": (2, "换药"),
    "nail": (3, "换药"),
    "burn": (2, "换药"),
    "excision": (7, "拆线/复诊"),
    "circumcision": (7, "复诊"),
}


def workbench(db: Session, day: date | None = None) -> dict:
    day = day or date.today()
    start = datetime.combine(day, datetime.min.time())
    end = datetime.combine(day, datetime.max.time())
    active = (
        db.query(TreatmentRoomCase)
        .filter(TreatmentRoomCase.status.in_(("waiting", "in_progress")))
        .order_by(TreatmentRoomCase.priority.desc(), TreatmentRoomCase.id)
        .all()
    )
    completed_today = (
        db.query(TreatmentRoomCase)
        .filter(
            TreatmentRoomCase.status == "completed",
            TreatmentRoomCase.completed_at >= start,
            TreatmentRoomCase.completed_at <= end,
        )
        .all()
    )
    cases = active + completed_today
    encounter_ids = [row.encounter_id for row in cases if row.encounter_id]
    pending_count = 0
    pending_amount = 0.0
    if encounter_ids:
        charges = (
            db.query(EncounterCharge)
            .filter(
                EncounterCharge.encounter_id.in_(encounter_ids),
                EncounterCharge.status == "pending",
                EncounterCharge.source_type.in_(("treatment_room", "procedure_material")),
            )
            .all()
        )
        pending_count = len(charges)
        pending_amount = round(sum(row.amount for row in charges), 2)
    overdue = (
        db.query(TreatmentFollowUp)
        .filter(TreatmentFollowUp.status == "pending", TreatmentFollowUp.due_date < day)
        .order_by(TreatmentFollowUp.due_date)
        .all()
    )
    due_today = (
        db.query(TreatmentFollowUp)
        .filter(TreatmentFollowUp.status == "pending", TreatmentFollowUp.due_date == day)
        .order_by(TreatmentFollowUp.id)
        .all()
    )
    kit_material_ids = {
        row.material_id for row in db.query(TreatmentTemplateMaterial).all()
    }
    low_stock = []
    for material_id in kit_material_ids:
        material = db.get(MaterialItem, material_id)
        quantity = (
            db.query(func.coalesce(func.sum(MaterialStock.quantity), 0))
            .filter(MaterialStock.item_id == material_id)
            .scalar()
            or 0
        )
        if quantity <= 10:
            low_stock.append(
                {
                    "material_id": material_id,
                    "name": material.name if material else f"#{material_id}",
                    "quantity": int(quantity),
                }
            )
    return {
        "date": day,
        "waiting": sum(1 for row in active if row.status == "waiting"),
        "in_progress": sum(1 for row in active if row.status == "in_progress"),
        "completed_today": len(completed_today),
        "pending_count": pending_count,
        "pending_amount": pending_amount,
        "overdue": [_followup_row(row) for row in overdue],
        "due_today": [_followup_row(row) for row in due_today],
        "low_stock": sorted(low_stock, key=lambda row: row["quantity"]),
        "cases": [
            {
                "id": row.id,
                "case_no": row.case_no,
                "patient_name": row.patient_name,
                "procedure_name": row.procedure_name,
                "template_code": row.template_code,
                "status": row.status,
                "priority": row.priority,
                "price": row.price,
                "created_at": row.created_at,
            }
            for row in cases
        ],
    }


def _followup_row(row: TreatmentFollowUp) -> dict:
    return {
        "id": row.id,
        "patient_name": row.patient_name,
        "due_date": row.due_date,
        "purpose": row.purpose,
        "note": row.note,
        "status": row.status,
    }


def reconciliation(db: Session, day: date | None = None) -> dict:
    day = day or date.today()
    start = datetime.combine(day, datetime.min.time())
    end = datetime.combine(day, datetime.max.time())
    cases = (
        db.query(TreatmentRoomCase, Patient)
        .join(Patient, TreatmentRoomCase.patient_id == Patient.id)
        .filter(
            TreatmentRoomCase.status == "completed",
            TreatmentRoomCase.completed_at >= start,
            TreatmentRoomCase.completed_at <= end,
        )
        .order_by(TreatmentRoomCase.id)
        .all()
    )
    rows = []
    totals = {"fee": 0.0, "material": 0.0, "total": 0.0, "paid": 0.0, "pending": 0.0, "cancelled": 0.0, "refunded": 0.0}
    for case, patient in cases:
        material_rows = (
            db.query(ProcedureMaterial)
            .filter(
                ProcedureMaterial.source_type == "treatment_room",
                ProcedureMaterial.source_id == case.id,
            )
            .all()
        )
        material_ids = {row.id for row in material_rows}
        charges = []
        if case.encounter_id is not None:
            candidates = (
                db.query(EncounterCharge)
                .filter(
                    EncounterCharge.encounter_id == case.encounter_id,
                    EncounterCharge.source_type.in_(("treatment_room", "procedure_material")),
                )
                .all()
            )
            charges = [
                charge
                for charge in candidates
                if (charge.source_type == "treatment_room" and charge.source_id == case.id)
                or (
                    charge.source_type == "procedure_material"
                    and charge.source_id in material_ids
                )
            ]
        fee = round(sum(row.amount for row in charges if row.charge_type == "treatment"), 2)
        material = round(sum(row.amount for row in charges if row.charge_type == "material"), 2)
        total = round(fee + material, 2)
        paid = round(sum(row.amount for row in charges if row.status == "paid"), 2)
        pending = round(sum(row.amount for row in charges if row.status == "pending"), 2)
        cancelled = round(sum(row.amount for row in charges if row.status == "cancelled"), 2)
        refunded = round(sum(row.amount for row in charges if row.status == "refunded"), 2)
        if not charges:
            status = "未计费"
        elif pending > 0:
            status = "待收费"
        elif paid >= total > 0:
            status = "已收费"
        elif cancelled >= total > 0:
            status = "已取消"
        else:
            status = "部分收费"
        rows.append(
            {
                "case_id": case.id,
                "case_no": case.case_no,
                "patient_name": patient.name,
                "procedure_name": case.procedure_name,
                "encounter_id": case.encounter_id,
                "fee": fee,
                "material": material,
                "total": total,
                "paid": paid,
                "pending": pending,
                "cancelled": cancelled,
                "refunded": refunded,
                "status": status,
            }
        )
        for key in totals:
            totals[key] = round(totals[key] + ({"fee": fee, "material": material, "total": total, "paid": paid, "pending": pending, "cancelled": cancelled, "refunded": refunded}[key]), 2)
    return {
        "date": day,
        "count": len(rows),
        "rows": rows,
        "totals": totals,
    }


def report(db: Session, report_date: date | None = None) -> dict:
    day = report_date or date.today()
    start = datetime.combine(day, datetime.min.time())
    end = datetime.combine(day, datetime.max.time())
    cases = (
        db.query(TreatmentRoomCase)
        .filter(TreatmentRoomCase.created_at >= start, TreatmentRoomCase.created_at <= end)
        .all()
    )
    completed = [row for row in cases if row.status == "completed"]
    material_amount = (
        db.query(func.coalesce(func.sum(ProcedureMaterial.amount), 0))
        .filter(
            ProcedureMaterial.source_type == "treatment_room",
            ProcedureMaterial.created_at >= start,
            ProcedureMaterial.created_at <= end,
        )
        .scalar()
        or 0
    )
    by_template: dict[str, int] = {}
    by_room: dict[str, int] = {}
    for row in completed:
        key = row.template_code or "other"
        by_template[key] = by_template.get(key, 0) + 1
        room = row.room_name or "未指定"
        by_room[room] = by_room.get(room, 0) + 1
    followups = (
        db.query(TreatmentFollowUp)
        .filter(
            TreatmentFollowUp.status == "pending",
            TreatmentFollowUp.due_date <= day,
        )
        .count()
    )
    return {
        "date": day,
        "total": len(cases),
        "completed": len(completed),
        "waiting": sum(1 for row in cases if row.status == "waiting"),
        "in_progress": sum(1 for row in cases if row.status == "in_progress"),
        "cancelled": sum(1 for row in cases if row.status == "cancelled"),
        "revenue": round(sum(row.price for row in completed), 2),
        "material_amount": round(float(material_amount), 2),
        "by_template": by_template,
        "by_room": by_room,
        "followups_due": followups,
    }


def _next_no(db: Session) -> str:
    last = db.query(TreatmentRoomCase.id).order_by(TreatmentRoomCase.id.desc()).first()
    return f"TR{datetime.now():%Y%m%d}{(last[0] if last else 0) + 1:04d}"


def create_case(db: Session, data: CaseCreate, requested_by: str = "") -> TreatmentRoomCase:
    if not get_patient(db, data.patient_id):
        raise ValueError("患者不存在")
    if data.encounter_id is not None and not get_encounter(db, data.encounter_id):
        raise ValueError("就诊记录不存在")
    if data.room_id is not None and not db.get(TreatmentRoom, data.room_id):
        raise ValueError("治疗室不存在")
    if data.template_code and data.template_code not in {row["code"] for row in TEMPLATES}:
        raise ValueError("处置模板不存在")
    if data.template_code:
        template = next(row for row in TEMPLATES if row["code"] == data.template_code)
        missing = [
            field["label"]
            for field in template["fields"]
            if field.get("required")
            and not str(data.template_data.get(field["key"], "")).strip()
        ]
        if missing:
            raise ValueError(f"请填写模板必填项：{'、'.join(missing)}")
    config = None
    if data.template_code:
        config = (
            db.query(TreatmentTemplateConfig)
            .filter(
                TreatmentTemplateConfig.template_code == data.template_code,
                TreatmentTemplateConfig.active.is_(True),
            )
            .first()
        )
    effective_charge_item = data.charge_item_id
    if effective_charge_item is None and config is not None:
        effective_charge_item = config.charge_item_id
    price = data.price
    if price == 0 and config is not None:
        price = config.price
    insurance_ratio = 0.0
    if effective_charge_item is not None:
        item = db.get(ChargeItem, effective_charge_item)
        if not item:
            raise ValueError("收费项目不存在")
        price = price or item.price
        insurance_ratio = item.insurance_ratio
    case = TreatmentRoomCase(
        case_no=_next_no(db),
        patient_id=data.patient_id,
        encounter_id=data.encounter_id,
        room_id=data.room_id,
        treatment_order_id=data.treatment_order_id,
        procedure_name=data.procedure_name,
        template_code=data.template_code,
        template_data=json.dumps(data.template_data, ensure_ascii=False) if data.template_data else "",
        diagnosis=data.diagnosis,
        priority=data.priority,
        charge_item_id=effective_charge_item,
        price=price,
        requested_by=requested_by,
        note=data.note,
    )
    db.add(case)
    db.flush()
    if data.encounter_id is not None and price > 0:
        add_charge(
            db,
            encounter_id=data.encounter_id,
            source_type="treatment_room",
            source_id=case.id,
            charge_type="treatment",
            charge_item_id=effective_charge_item,
            item_name=f"治疗室：{data.procedure_name}",
            quantity=1,
            unit_price=price,
            insurance_ratio=insurance_ratio,
        )
    db.commit()
    db.refresh(case)
    return case


def repeat_case(
    db: Session, case_id: int, requested_by: str = ""
) -> TreatmentRoomCase:
    """按上一次治疗复诊：复制处置，不新建挂号/就诊，仍生成收费。"""
    original = get_case(db, case_id)
    if not original:
        raise ValueError("原处置不存在")
    if original.status != "completed":
        raise ValueError("只能按已完成的治疗复诊")
    pending = (
        db.query(TreatmentRoomCase)
        .filter(
            TreatmentRoomCase.repeat_of_case_id == case_id,
            TreatmentRoomCase.status.in_(("waiting", "in_progress")),
        )
        .first()
    )
    if pending:
        raise ValueError(f"该治疗已有未完成的复诊处置 {pending.case_no}")
    case = TreatmentRoomCase(
        case_no=_next_no(db),
        patient_id=original.patient_id,
        encounter_id=original.encounter_id,
        room_id=original.room_id,
        procedure_name=original.procedure_name,
        template_code=original.template_code,
        template_data=original.template_data,
        diagnosis=original.diagnosis,
        priority="routine",
        charge_item_id=original.charge_item_id,
        price=original.price,
        requested_by=requested_by,
        note=f"按上次治疗复诊：{original.case_no}",
        visit_type="follow_up",
        repeat_of_case_id=original.id,
    )
    db.add(case)
    db.flush()
    if case.encounter_id is not None and case.price > 0:
        insurance_ratio = 0.0
        if case.charge_item_id is not None:
            item = db.get(ChargeItem, case.charge_item_id)
            insurance_ratio = item.insurance_ratio if item else 0.0
        add_charge(
            db,
            encounter_id=case.encounter_id,
            source_type="treatment_room",
            source_id=case.id,
            charge_type="treatment",
            charge_item_id=case.charge_item_id,
            item_name=f"治疗室复诊：{case.procedure_name}",
            quantity=1,
            unit_price=case.price,
            insurance_ratio=insurance_ratio,
        )
    db.commit()
    db.refresh(case)
    return case


def list_cases(db: Session, status: str | None = None) -> list[dict]:
    query = db.query(TreatmentRoomCase, Patient).join(
        Patient, TreatmentRoomCase.patient_id == Patient.id
    )
    if status:
        query = query.filter(TreatmentRoomCase.status == status)
    rows = query.order_by(TreatmentRoomCase.id.desc()).all()
    return [
        {
            "id": case.id,
            "case_no": case.case_no,
            "patient_id": case.patient_id,
            "patient_name": patient.name,
            "encounter_id": case.encounter_id,
            "room_id": case.room_id,
            "room_name": case.room_name,
            "procedure_name": case.procedure_name,
            "template_code": case.template_code,
            "template_data": case.template_data,
            "diagnosis": case.diagnosis,
            "status": case.status,
            "priority": case.priority,
            "price": case.price,
            "consent": case.consent,
            "operator": case.operator,
            "started_at": case.started_at,
            "completed_at": case.completed_at,
            "visit_type": case.visit_type,
            "repeat_of_case_id": case.repeat_of_case_id,
        }
        for case, patient in rows
    ]


def get_case(db: Session, case_id: int) -> TreatmentRoomCase | None:
    return db.get(TreatmentRoomCase, case_id)


def start_case(db: Session, case_id: int, data: StartRequest, operator: str = "") -> TreatmentRoomCase:
    case = get_case(db, case_id)
    if not case:
        raise ValueError("治疗室病例不存在")
    if case.status != "waiting":
        raise ValueError("该病例当前状态不可开始")
    if not data.consent:
        raise ValueError("请先完成知情同意")
    if not data.consent_signer.strip():
        raise ValueError("请填写知情同意签署人")
    if not data.consent_signature_path.strip():
        raise ValueError("请上传知情同意签名图片")
    config = None
    if case.template_code:
        config = (
            db.query(TreatmentTemplateConfig)
            .filter(
                TreatmentTemplateConfig.template_code == case.template_code,
                TreatmentTemplateConfig.active.is_(True),
            )
            .first()
        )
    if config and config.materials and not case.kit_applied:
        from app.modules.procedure_materials.service import consume_material

        try:
            for line in config.materials:
                consume_material(
                    db,
                    source_type="treatment_room",
                    source_id=case.id,
                    encounter_id=case.encounter_id,
                    material_id=line.material_id,
                    quantity=line.quantity,
                    warehouse=line.warehouse or "总库",
                    operator=operator,
                    commit=False,
                )
            case.kit_applied = True
        except ValueError as e:
            db.rollback()
            raise ValueError(f"模板套餐耗材扣减失败：{e}")
    case.status = "in_progress"
    case.consent = True
    case.consent_version = data.consent_version or "v1"
    case.consent_signer = data.consent_signer.strip()
    case.consent_relation = data.consent_relation.strip() or "本人"
    case.consent_signature_path = data.consent_signature_path.strip()
    case.consent_signed_at = datetime.now()
    case.anesthesia = data.anesthesia
    case.findings = data.findings
    case.operator = operator
    case.started_at = datetime.now()
    db.commit()
    db.refresh(case)
    return case


def complete_case(db: Session, case_id: int, data: CompleteRequest, operator: str = "") -> TreatmentRoomCase:
    case = get_case(db, case_id)
    if not case:
        raise ValueError("治疗室病例不存在")
    if case.status != "in_progress":
        raise ValueError("只有处置中的病例可以完成")
    case.status = "completed"
    case.findings = data.findings or case.findings
    case.procedure_detail = data.procedure_detail
    case.sutures = data.sutures
    case.dressing = data.dressing
    case.materials = data.materials
    case.complications = data.complications
    case.note = data.note or case.note
    case.operator = operator or case.operator
    case.completed_at = datetime.now()
    plan = _FOLLOWUP_PLAN.get(case.template_code)
    if plan:
        days, purpose = plan
        db.add(
            TreatmentFollowUp(
                case_id=case.id,
                patient_id=case.patient_id,
                encounter_id=case.encounter_id,
                due_date=(case.completed_at + timedelta(days=days)).date(),
                purpose=purpose,
                note=f"{case.procedure_name}后{purpose}",
            )
        )
    db.commit()
    db.refresh(case)
    return case


def cancel_case(db: Session, case_id: int, operator: str = "") -> TreatmentRoomCase:
    case = get_case(db, case_id)
    if not case:
        raise ValueError("治疗室病例不存在")
    if case.status in ("completed", "cancelled"):
        raise ValueError("该病例已结束")
    used = (
        db.query(ProcedureMaterial)
        .filter(
            ProcedureMaterial.source_type == "treatment_room",
            ProcedureMaterial.source_id == case.id,
            ProcedureMaterial.returned_at.is_(None),
        )
        .all()
    )
    charges = []
    if case.encounter_id is not None:
        charges = (
            db.query(EncounterCharge)
            .filter(
                EncounterCharge.encounter_id == case.encounter_id,
                EncounterCharge.status != "cancelled",
                EncounterCharge.source_type.in_(("treatment_room", "procedure_material")),
            )
            .all()
        )
        charges = [
            charge
            for charge in charges
            if (charge.source_type == "treatment_room" and charge.source_id == case.id)
            or (
                charge.source_type == "procedure_material"
                and charge.source_id in {row.id for row in used}
            )
        ]
        if any(charge.status == "paid" for charge in charges):
            raise ValueError("该处置已收费，请先在收费处退费后再取消")
    for row in used:
        material = db.get(MaterialItem, row.material_id)
        stock = (
            db.query(MaterialStock)
            .filter(
                MaterialStock.item_id == row.material_id,
                MaterialStock.warehouse == row.warehouse,
            )
            .first()
        )
        if stock is None:
            stock = MaterialStock(
                item_id=row.material_id, warehouse=row.warehouse, quantity=0
            )
            db.add(stock)
        stock.quantity += row.quantity
        if material is not None:
            record_material(
                db,
                material,
                warehouse=row.warehouse,
                direction="in",
                quantity=row.quantity,
                unit_price=row.unit_price,
                ref_type="treatment_room_cancel",
                ref_id=row.id,
                operator=operator,
                note=f"取消处置退耗材：{case.case_no}",
            )
        row.returned_at = datetime.now()
    for charge in charges:
        charge.status = "cancelled"
    case.kit_applied = False
    case.status = "cancelled"
    case.note = (case.note + "；" if case.note else "") + f"取消（{operator}）"
    db.commit()
    db.refresh(case)
    return case


def add_material(db: Session, case_id: int, data, operator: str = ""):
    from app.modules.procedure_materials.service import consume_material

    case = get_case(db, case_id)
    if not case:
        raise ValueError("治疗室病例不存在")
    if case.status not in ("in_progress", "completed"):
        raise ValueError("只有处置中/已完成的病例可以登记耗材")
    return consume_material(
        db,
        source_type="treatment_room",
        source_id=case.id,
        encounter_id=case.encounter_id,
        material_id=data.material_id,
        quantity=data.quantity,
        warehouse=data.warehouse,
        operator=operator,
    )
