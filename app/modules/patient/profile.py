"""患者 360：基本信息、就诊时间线、预约、病案档案、费用统计。"""
from sqlalchemy.orm import Session

from app.modules.appointment.models import Appointment
from app.modules.archive.models import ArchiveRecord
from app.modules.patient.service import get_patient
from app.modules.staff.models import Doctor

from .history import get_patient_history


def patient_profile(db: Session, patient_id: int) -> dict | None:
    patient = get_patient(db, patient_id)
    if not patient:
        return None
    history = get_patient_history(db, patient_id) or {"encounters": []}
    encounters = history["encounters"]

    appointments = (
        db.query(Appointment)
        .filter(Appointment.patient_id == patient_id)
        .order_by(Appointment.id.desc())
        .all()
    )
    appointment_rows = []
    for row in appointments:
        doctor = db.get(Doctor, row.doctor_id)
        appointment_rows.append(
            {
                "id": row.id,
                "doctor_id": row.doctor_id,
                "doctor_name": doctor.name if doctor else "",
                "status": row.status,
                "created_at": row.created_at,
                "checked_in_at": row.checked_in_at,
                "registration_id": row.registration_id,
            }
        )

    archives = (
        db.query(ArchiveRecord)
        .filter(ArchiveRecord.patient_id == patient_id)
        .order_by(ArchiveRecord.id.desc())
        .all()
    )
    archive_rows = [
        {
            "id": row.id,
            "archive_no": row.archive_no,
            "record_type": row.record_type,
            "status": row.status,
            "storage_location": row.storage_location,
            "page_count": row.page_count,
            "archived_at": row.archived_at,
        }
        for row in archives
    ]

    total_paid = round(
        sum(
            payment["amount"]
            - payment.get("refunded_amount", 0)
            for encounter in encounters
            for payment in encounter["payments"]
        ),
        2,
    )
    outstanding = round(
        sum(
            charge["amount"]
            for encounter in encounters
            for charge in encounter["charges"]
            if charge["status"] == "pending"
        ),
        2,
    )
    prescription_count = sum(len(encounter["prescriptions"]) for encounter in encounters)
    lab_count = sum(len(encounter["lab_requests"]) for encounter in encounters)
    visit_dates = [encounter["visited_at"] for encounter in encounters]
    return {
        "patient": history["patient"],
        "stats": {
            "visit_count": len(encounters),
            "appointment_count": len(appointments),
            "archive_count": len(archives),
            "prescription_count": prescription_count,
            "lab_count": lab_count,
            "total_paid": total_paid,
            "outstanding": outstanding,
            "last_visit": max(visit_dates) if visit_dates else None,
        },
        "appointments": appointment_rows,
        "archives": archive_rows,
        "encounters": encounters,
    }
