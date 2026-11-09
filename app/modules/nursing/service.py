"""护士站输液/医嘱执行：同步医嘱、配药、座位、巡视、完成。"""
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.modules.encounter.models import Encounter, PrescriptionItem
from app.modules.encounter.service import get_encounter
from app.modules.patient.models import Patient
from app.modules.registration.models import Registration
from app.modules.staff.models import Doctor
from app.modules.treatment.models import TreatmentOrder

from .models import NursingObservation, NursingOrder, NursingPreparation
from .schemas import (
    CompleteRequest,
    ObserveRequest,
    PrepareRequest,
    SkipRequest,
    StartRequest,
)


def _nursing_type(route: str) -> str | None:
    text = route or ""
    if any(key in text for key in ("静滴", "静脉滴", "输液", "滴注")):
        return "infusion"
    if any(key in text for key in ("静推", "肌注", "皮下", "注射")):
        return "injection"
    return None


def sync_orders(db: Session, encounter_id: int) -> list[NursingOrder]:
    """从静滴/注射类处方和治疗单生成护士执行单，重复同步不重复建。"""
    if not get_encounter(db, encounter_id):
        raise ValueError("就诊记录不存在")
    created = []
    prescriptions = (
        db.query(PrescriptionItem)
        .filter(PrescriptionItem.encounter_id == encounter_id)
        .all()
    )
    for item in prescriptions:
        order_type = _nursing_type(item.route)
        if not order_type:
            continue
        exists = (
            db.query(NursingOrder)
            .filter(
                NursingOrder.source_type == "prescription",
                NursingOrder.source_id == item.id,
            )
            .first()
        )
        if exists:
            continue
        row = NursingOrder(
            encounter_id=encounter_id,
            source_type="prescription",
            source_id=item.id,
            order_type=order_type,
            item_name=item.drug_name,
            dosage=item.dosage,
            route=item.route,
            frequency=item.frequency,
        )
        db.add(row)
        created.append(row)
    treatments = (
        db.query(TreatmentOrder)
        .filter(
            TreatmentOrder.encounter_id == encounter_id,
            TreatmentOrder.status == "pending",
        )
        .all()
    )
    for item in treatments:
        exists = (
            db.query(NursingOrder)
            .filter(
                NursingOrder.source_type == "treatment",
                NursingOrder.source_id == item.id,
            )
            .first()
        )
        if exists:
            continue
        row = NursingOrder(
            encounter_id=encounter_id,
            source_type="treatment",
            source_id=item.id,
            order_type="treatment",
            item_name=item.item_name,
            dosage=str(item.quantity),
            route="治疗",
            note=item.note,
        )
        db.add(row)
        created.append(row)
    db.commit()
    return created


def list_orders(
    db: Session,
    status: str | None = None,
    encounter_id: int | None = None,
) -> list[dict]:
    query = (
        db.query(NursingOrder, Patient)
        .join(Encounter, NursingOrder.encounter_id == Encounter.id)
        .join(Registration, Encounter.registration_id == Registration.id)
        .join(Patient, Registration.patient_id == Patient.id)
    )
    if status:
        statuses = [item.strip() for item in status.split(",") if item.strip()]
        if statuses:
            query = query.filter(NursingOrder.status.in_(statuses))
    if encounter_id:
        query = query.filter(NursingOrder.encounter_id == encounter_id)
    rows = query.order_by(NursingOrder.id.desc()).all()
    result = []
    for order, patient in rows:
        encounter = get_encounter(db, order.encounter_id)
        registration = db.get(Registration, encounter.registration_id) if encounter else None
        doctor = db.get(Doctor, registration.doctor_id) if registration else None
        result.append(
            {
                "id": order.id,
                "encounter_id": order.encounter_id,
                "patient_id": patient.id,
                "patient_name": patient.name,
                "doctor_name": doctor.name if doctor else "",
                "diagnosis": encounter.diagnosis if encounter else "",
                "order_type": order.order_type,
                "item_name": order.item_name,
                "dosage": order.dosage,
                "route": order.route,
                "frequency": order.frequency,
                "status": order.status,
                "priority": order.priority,
                "seat_no": order.seat_no,
                "rate_ml_h": order.rate_ml_h,
                "started_at": order.started_at,
                "completed_at": order.completed_at,
                "adverse_reaction": order.adverse_reaction,
            }
        )
    return result


def get_order(db: Session, order_id: int) -> NursingOrder | None:
    return db.get(NursingOrder, order_id)


def prepare(
    db: Session, order_id: int, data: PrepareRequest, operator: str = ""
) -> NursingPreparation:
    order = get_order(db, order_id)
    if not order:
        raise ValueError("执行单不存在")
    if order.status != "pending":
        raise ValueError("该执行单当前状态不可配药")
    row = NursingPreparation(
        order_id=order.id,
        solvent=data.solvent,
        dose=data.dose,
        batch_no=data.batch_no,
        prepared_by=operator,
        checked_by=data.checked_by,
        expires_at=datetime.now() + timedelta(minutes=data.expires_minutes),
        note=data.note,
    )
    order.status = "prepared"
    order.prepared_by = operator
    order.prepared_at = datetime.now()
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def start(db: Session, order_id: int, data: StartRequest, operator: str = "") -> NursingOrder:
    order = get_order(db, order_id)
    if not order:
        raise ValueError("执行单不存在")
    if order.status not in ("pending", "prepared"):
        raise ValueError("该执行单当前状态不可开始")
    order.status = "executing"
    order.seat_no = data.seat_no
    order.rate_ml_h = data.rate_ml_h
    order.started_at = datetime.now()
    order.executed_by = operator
    db.commit()
    db.refresh(order)
    return order


def observe(
    db: Session, order_id: int, data: ObserveRequest, operator: str = ""
) -> NursingObservation:
    order = get_order(db, order_id)
    if not order:
        raise ValueError("执行单不存在")
    if order.status != "executing":
        raise ValueError("只有执行中的输液/治疗可以巡视")
    row = NursingObservation(
        order_id=order.id,
        rate_ml_h=data.rate_ml_h,
        note=data.note,
        adverse_reaction=data.adverse_reaction or None,
        nurse=operator,
    )
    if data.rate_ml_h is not None:
        order.rate_ml_h = data.rate_ml_h
    if data.adverse_reaction:
        order.adverse_reaction = data.adverse_reaction
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def complete(
    db: Session, order_id: int, data: CompleteRequest, operator: str = ""
) -> NursingOrder:
    order = get_order(db, order_id)
    if not order:
        raise ValueError("执行单不存在")
    if order.status != "executing":
        raise ValueError("只有执行中的执行单可以完成")
    order.status = "completed"
    order.completed_at = datetime.now()
    order.executed_by = operator
    order.note = data.note or order.note
    order.adverse_reaction = data.adverse_reaction or order.adverse_reaction
    db.commit()
    db.refresh(order)
    return order


def skip(db: Session, order_id: int, data: SkipRequest, operator: str = "") -> NursingOrder:
    order = get_order(db, order_id)
    if not order:
        raise ValueError("执行单不存在")
    if order.status not in ("pending", "prepared"):
        raise ValueError("该执行单当前状态不可跳过")
    order.status = "skipped"
    order.note = (order.note + "；" if order.note else "") + f"跳过：{data.reason}（{operator}）"
    order.executed_by = operator
    db.commit()
    db.refresh(order)
    return order


def detail(db: Session, order_id: int) -> dict:
    order = get_order(db, order_id)
    if not order:
        raise ValueError("执行单不存在")
    return {
        "order": order,
        "preparations": order.preparations,
        "observations": order.observations,
    }
