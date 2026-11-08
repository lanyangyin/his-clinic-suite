from datetime import date, datetime, time

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.modules.appointment.models import Appointment
from app.modules.auth.models import User
from app.modules.billing.models import Payment
from app.modules.charges.models import EncounterCharge
from app.modules.drug.models import Drug
from app.modules.encounter.models import Encounter, PrescriptionItem
from app.modules.patient.models import Patient
from app.modules.staff.models import Department, Doctor


def dashboard_stats(db: Session) -> dict:
    """管理台仪表盘统计（只读聚合，admin 专用）。"""
    today_start = datetime.combine(date.today(), time.min)

    return {
        "patients": db.query(func.count(Patient.id)).scalar() or 0,
        "departments": db.query(func.count(Department.id)).scalar() or 0,
        "doctors": db.query(func.count(Doctor.id)).scalar() or 0,
        "drugs": db.query(func.count(Drug.id)).scalar() or 0,
        "users": db.query(func.count(User.id)).scalar() or 0,
        "encounters_today": db.query(func.count(Encounter.id))
        .filter(Encounter.created_at >= today_start)
        .scalar()
        or 0,
        "prescription_items_today": db.query(func.count(PrescriptionItem.id))
        .filter(PrescriptionItem.created_at >= today_start)
        .scalar()
        or 0,
        "payments_today_count": db.query(func.count(Payment.id))
        .filter(Payment.created_at >= today_start, Payment.status == "paid")
        .scalar()
        or 0,
        "payments_today_amount": round(
            db.query(func.sum(Payment.amount))
            .filter(Payment.created_at >= today_start, Payment.status == "paid")
            .scalar()
            or 0.0,
            2,
        ),
        "pending_charges": db.query(func.count(EncounterCharge.id))
        .filter(EncounterCharge.status == "pending")
        .scalar()
        or 0,
        "appointments_booked": db.query(func.count(Appointment.id))
        .filter(Appointment.status == "booked")
        .scalar()
        or 0,
    }
