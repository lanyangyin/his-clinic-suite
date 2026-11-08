from sqlalchemy import func
from sqlalchemy.orm import Session

from app.modules.billing.models import Payment
from app.modules.encounter.models import Encounter, PrescriptionItem
from app.modules.inpatient.models import Admission, InpatientOrder
from app.modules.registration.models import Registration
from app.modules.staff.service import list_doctors


def doctor_performance(db: Session, doctor_id: int | None = None) -> list[dict]:
    """医生绩效：接诊/处方/门诊收入/住院患者/医嘱 工作量统计。"""
    def _rows(query):
        if doctor_id is not None:
            query = query.filter(Registration.doctor_id == doctor_id)
        return {row[0]: row[1] for row in query.group_by(Registration.doctor_id).all()}

    encounters = _rows(
        db.query(Registration.doctor_id, func.count(Encounter.id)).join(
            Encounter, Encounter.registration_id == Registration.id
        )
    )
    prescriptions = _rows(
        db.query(Registration.doctor_id, func.count(PrescriptionItem.id))
        .join(Encounter, Encounter.registration_id == Registration.id)
        .join(PrescriptionItem, PrescriptionItem.encounter_id == Encounter.id)
    )
    revenue = _rows(
        db.query(Registration.doctor_id, func.sum(Payment.amount))
        .join(Encounter, Encounter.registration_id == Registration.id)
        .join(Payment, Payment.encounter_id == Encounter.id)
        .filter(Payment.status == "paid")
    )

    admissions_query = db.query(Admission.doctor_id, func.count(Admission.id))
    orders_query = db.query(InpatientOrder.doctor_id, func.count(InpatientOrder.id))
    if doctor_id is not None:
        admissions_query = admissions_query.filter(Admission.doctor_id == doctor_id)
        orders_query = orders_query.filter(InpatientOrder.doctor_id == doctor_id)
    admissions = {row[0]: row[1] for row in admissions_query.group_by(Admission.doctor_id).all()}
    orders = {row[0]: row[1] for row in orders_query.group_by(InpatientOrder.doctor_id).all()}

    result = []
    doctors = list_doctors(db)
    if doctor_id is not None:
        doctors = [doc for doc in doctors if doc.id == doctor_id]
    for doctor in doctors:
        result.append(
            {
                "doctor_id": doctor.id,
                "doctor_name": doctor.name,
                "encounters": int(encounters.get(doctor.id, 0)),
                "prescriptions": int(prescriptions.get(doctor.id, 0)),
                "outpatient_revenue": round(float(revenue.get(doctor.id, 0) or 0), 2),
                "admissions": int(admissions.get(doctor.id, 0)),
                "orders": int(orders.get(doctor.id, 0)),
            }
        )
    return result
