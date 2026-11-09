"""患者历史诊疗聚合：一次返回历次就诊的病历、处方、检验、治疗、收费。"""
from sqlalchemy.orm import Session

from app.modules.billing.service import list_payments
from app.modules.charges.service import list_charges
from app.modules.encounter.models import Encounter
from app.modules.encounter.service import get_medical_record, list_prescription_items
from app.modules.lis.service import list_requests
from app.modules.patient.service import get_patient
from app.modules.registration.models import Registration
from app.modules.staff.models import Doctor
from app.modules.treatment.service import list_treatments

_RECORD_FIELDS = (
    "chief_complaint",
    "present_illness",
    "past_history",
    "physical_exam",
    "treatment_advice",
    "written_by",
    "signed_by",
    "created_at",
    "signed_at",
)


def get_patient_history(db: Session, patient_id: int) -> dict | None:
    patient = get_patient(db, patient_id)
    if not patient:
        return None

    rows = (
        db.query(Encounter, Registration)
        .join(Registration, Encounter.registration_id == Registration.id)
        .filter(Registration.patient_id == patient_id)
        .order_by(Encounter.id.desc())
        .all()
    )
    encounters = []
    for encounter, registration in rows:
        doctor = db.get(Doctor, registration.doctor_id)
        record = get_medical_record(db, encounter.id)
        prescriptions = list_prescription_items(db, encounter.id)
        labs = list_requests(db, encounter.id)
        treatments = list_treatments(db, encounter.id)
        charges = list_charges(db, encounter.id)
        payments = list_payments(db, encounter_id=encounter.id)
        encounters.append(
            {
                "id": encounter.id,
                "registration_id": encounter.registration_id,
                "diagnosis": encounter.diagnosis,
                "status": encounter.status,
                "visited_at": encounter.created_at,
                "doctor_id": registration.doctor_id,
                "doctor_name": doctor.name if doctor else "",
                "medical_record": (
                    {key: getattr(record, key) for key in _RECORD_FIELDS}
                    if record
                    else None
                ),
                "prescriptions": [
                    {
                        "id": item.id,
                        "drug_id": item.drug_id,
                        "drug_name": item.drug_name,
                        "quantity": item.quantity,
                        "unit_price": item.unit_price,
                        "dosage": item.dosage,
                        "frequency": item.frequency,
                        "route": item.route,
                        "days": item.days,
                        "amount": round(item.unit_price * item.quantity, 2),
                        "insurance_category": item.insurance_category,
                    }
                    for item in prescriptions
                ],
                "lab_requests": [
                    {
                        "id": item.id,
                        "item_name": item.item_name,
                        "status": item.status,
                        "result": item.result,
                        "result_value": item.result_value,
                        "result_unit": item.result_unit,
                        "reference_low": item.reference_low,
                        "reference_high": item.reference_high,
                        "abnormal_flag": item.abnormal_flag,
                        "critical_flag": item.critical_flag,
                        "report_no": item.report_no,
                        "requested_at": item.requested_at,
                        "reported_at": item.reported_at,
                    }
                    for item in labs
                ],
                "treatments": [
                    {
                        "id": item.id,
                        "item_name": item.item_name,
                        "quantity": item.quantity,
                        "note": item.note,
                        "status": item.status,
                        "executed_by": item.executed_by,
                        "executed_at": item.executed_at,
                    }
                    for item in treatments
                ],
                "charges": [
                    {
                        "id": item.id,
                        "item_name": item.item_name,
                        "quantity": item.quantity,
                        "unit_price": item.unit_price,
                        "amount": item.amount,
                        "refunded_quantity": item.refunded_quantity,
                        "status": item.status,
                    }
                    for item in charges
                ],
                "payments": [
                    {
                        "id": item.id,
                        "amount": item.amount,
                        "insurance_amount": item.insurance_amount,
                        "self_pay_amount": item.self_pay_amount,
                        "status": item.status,
                        "channel": item.channel,
                        "created_at": item.created_at,
                    }
                    for item in payments
                ],
            }
        )

    return {
        "patient": {
            "id": patient.id,
            "name": patient.name,
            "phone": patient.phone,
            "id_number": patient.id_number,
        },
        "encounters": encounters,
    }
