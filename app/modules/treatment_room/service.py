"""治疗室：清创/换药/小处置的排队、知情同意、处置记录与计费。"""
from datetime import date, datetime, timedelta
import json

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.modules.charges.models import ChargeItem
from app.modules.charges.service import add_charge
from app.modules.encounter.service import get_encounter
from app.modules.patient.models import Patient
from app.modules.patient.service import get_patient

from .models import TreatmentFollowUp, TreatmentRoom, TreatmentRoomCase
from .schemas import CaseCreate, CompleteRequest, FollowUpCreate, RoomCreate, StartRequest
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


def list_templates() -> list[dict]:
    return TEMPLATES


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


def complete_followup(db: Session, followup_id: int) -> TreatmentFollowUp:
    row = db.get(TreatmentFollowUp, followup_id)
    if not row:
        raise ValueError("随访任务不存在")
    if row.status != "pending":
        raise ValueError("该随访任务已结束")
    row.status = "completed"
    row.completed_at = datetime.now()
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
    price = data.price
    insurance_ratio = 0.0
    if data.charge_item_id is not None:
        item = db.get(ChargeItem, data.charge_item_id)
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
        charge_item_id=data.charge_item_id,
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
            charge_item_id=data.charge_item_id,
            item_name=f"治疗室：{data.procedure_name}",
            quantity=1,
            unit_price=price,
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
    case.status = "in_progress"
    case.consent = True
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
