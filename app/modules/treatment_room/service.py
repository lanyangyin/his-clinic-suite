"""治疗室：清创/换药/小处置的排队、知情同意、处置记录与计费。"""
from datetime import datetime

from sqlalchemy.orm import Session

from app.modules.charges.models import ChargeItem
from app.modules.charges.service import add_charge
from app.modules.encounter.service import get_encounter
from app.modules.patient.models import Patient
from app.modules.patient.service import get_patient

from .models import TreatmentRoom, TreatmentRoomCase
from .schemas import CaseCreate, CompleteRequest, RoomCreate, StartRequest


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
