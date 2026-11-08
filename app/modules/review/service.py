from datetime import date, datetime, time

from sqlalchemy.orm import Session

from app.modules.drug.models import Drug
from app.modules.encounter.models import Encounter, PrescriptionItem
from app.modules.patient.service import get_patient
from app.modules.registration.service import get_registration
from app.modules.staff.service import get_doctor

_INJECTION_KEYWORDS = ("注射", "静滴", "输液", "肌注", "静注")


def _base_query(db: Session, start_date: date | None, end_date: date | None):
    query = (
        db.query(PrescriptionItem, Drug, Encounter)
        .join(Drug, Drug.id == PrescriptionItem.drug_id)
        .join(Encounter, Encounter.id == PrescriptionItem.encounter_id)
    )
    if start_date is not None:
        query = query.filter(
            Encounter.created_at >= datetime.combine(start_date, time.min)
        )
    if end_date is not None:
        query = query.filter(
            Encounter.created_at <= datetime.combine(end_date, time.max)
        )
    return query


def summary(
    db: Session, start_date: date | None = None, end_date: date | None = None
) -> dict:
    """处方点评汇总：处方数/条目数/均金额/抗菌药物使用率/注射剂使用率。"""
    rows = _base_query(db, start_date, end_date).all()
    if not rows:
        return {
            "prescription_count": 0,
            "item_count": 0,
            "avg_items": 0.0,
            "total_amount": 0.0,
            "avg_amount": 0.0,
            "antibiotic_prescriptions": 0,
            "antibiotic_rate": 0.0,
            "injection_prescriptions": 0,
            "injection_rate": 0.0,
        }

    encounter_ids = set()
    antibiotic_ids = set()
    injection_ids = set()
    total_amount = 0.0
    for item, drug, encounter in rows:
        encounter_ids.add(item.encounter_id)
        total_amount += item.quantity * item.unit_price
        if drug.antibiotic_level >= 1:
            antibiotic_ids.add(item.encounter_id)
        if any(keyword in (item.route or "") for keyword in _INJECTION_KEYWORDS):
            injection_ids.add(item.encounter_id)

    prescription_count = len(encounter_ids)
    item_count = len(rows)
    total_amount = round(total_amount, 2)
    return {
        "prescription_count": prescription_count,
        "item_count": item_count,
        "avg_items": round(item_count / prescription_count, 2),
        "total_amount": total_amount,
        "avg_amount": round(total_amount / prescription_count, 2),
        "antibiotic_prescriptions": len(antibiotic_ids),
        "antibiotic_rate": round(len(antibiotic_ids) / prescription_count, 4),
        "injection_prescriptions": len(injection_ids),
        "injection_rate": round(len(injection_ids) / prescription_count, 4),
    }


def issues(
    db: Session, start_date: date | None = None, end_date: date | None = None
) -> list[dict]:
    """可疑处方明细：医保超量提醒、单次超量（>5）。"""
    rows = _base_query(db, start_date, end_date).all()
    result = []
    for item, drug, encounter in rows:
        reason = ""
        if item.insurance_warning:
            reason = item.insurance_warning
        elif item.quantity > 5:
            reason = "单次开立数量超量（>5）"
        if not reason:
            continue
        registration = get_registration(db, encounter.registration_id)
        patient = get_patient(db, registration.patient_id) if registration else None
        doctor = get_doctor(db, registration.doctor_id) if registration else None
        result.append(
            {
                "encounter_id": item.encounter_id,
                "patient_name": patient.name if patient else "",
                "doctor_name": doctor.name if doctor else "",
                "drug_name": drug.name,
                "quantity": item.quantity,
                "unit_price": item.unit_price,
                "amount": round(item.quantity * item.unit_price, 2),
                "reason": reason,
            }
        )
    return result


def detail(db: Session, encounter_id: int) -> dict:
    """单张处方详情（点评用）。"""
    encounter = db.get(Encounter, encounter_id)
    if not encounter:
        raise ValueError("就诊记录不存在")
    registration = get_registration(db, encounter.registration_id)
    patient = get_patient(db, registration.patient_id) if registration else None
    doctor = get_doctor(db, registration.doctor_id) if registration else None

    items = (
        db.query(PrescriptionItem, Drug)
        .join(Drug, Drug.id == PrescriptionItem.drug_id)
        .filter(PrescriptionItem.encounter_id == encounter_id)
        .order_by(PrescriptionItem.id)
        .all()
    )
    return {
        "encounter_id": encounter.id,
        "patient_name": patient.name if patient else "",
        "doctor_name": doctor.name if doctor else "",
        "diagnosis": encounter.diagnosis,
        "items": [
            {
                "drug_name": drug.name,
                "quantity": item.quantity,
                "unit_price": item.unit_price,
                "amount": round(item.quantity * item.unit_price, 2),
                "dosage": item.dosage,
                "frequency": item.frequency,
                "route": item.route,
                "days": item.days,
                "antibiotic_level": drug.antibiotic_level,
            }
            for item, drug in items
        ],
        "total_amount": round(
            sum(item.quantity * item.unit_price for item, _ in items), 2
        ),
    }
