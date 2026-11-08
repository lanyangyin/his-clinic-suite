from sqlalchemy.orm import Session

from app.modules.encounter.models import Encounter
from app.modules.lis.models import LabRequest
from app.modules.pacs.models import ImagingRequest
from app.modules.patient.service import get_patient_by_id_number
from app.modules.registration.models import Registration


def _patient_encounter_ids(db: Session, patient_id: int) -> list[int]:
    rows = (
        db.query(Encounter.id)
        .join(Registration, Registration.id == Encounter.registration_id)
        .filter(Registration.patient_id == patient_id)
        .all()
    )
    return [row[0] for row in rows]


def get_portal_patient(db: Session, id_number: str) -> dict:
    """患者自助查询：基本信息 + 挂号记录 + 最近就诊。"""
    patient = get_patient_by_id_number(db, id_number)
    if not patient:
        raise ValueError("患者不存在")

    registrations = (
        db.query(Registration)
        .filter(Registration.patient_id == patient.id)
        .order_by(Registration.id.desc())
        .limit(10)
        .all()
    )
    encounters = (
        db.query(Encounter)
        .join(Registration, Registration.id == Encounter.registration_id)
        .filter(Registration.patient_id == patient.id)
        .order_by(Encounter.id.desc())
        .limit(10)
        .all()
    )
    return {
        "id": patient.id,
        "name": patient.name,
        "id_number": patient.id_number,
        "phone": patient.phone,
        "registrations": [
            {"id": row.id, "doctor_id": row.doctor_id, "status": row.status}
            for row in registrations
        ],
        "encounters": [
            {"id": row.id, "diagnosis": row.diagnosis, "status": row.status}
            for row in encounters
        ],
    }


def get_portal_reports(db: Session, id_number: str) -> dict:
    """患者自助查询：已出结果的检验/检查报告。"""
    patient = get_patient_by_id_number(db, id_number)
    if not patient:
        raise ValueError("患者不存在")

    encounter_ids = _patient_encounter_ids(db, patient.id)
    labs = []
    imaging = []
    if encounter_ids:
        labs = (
            db.query(LabRequest)
            .filter(
                LabRequest.encounter_id.in_(encounter_ids),
                LabRequest.status == "reported",
            )
            .order_by(LabRequest.id.desc())
            .all()
        )
        imaging = (
            db.query(ImagingRequest)
            .filter(
                ImagingRequest.encounter_id.in_(encounter_ids),
                ImagingRequest.status == "reported",
            )
            .order_by(ImagingRequest.id.desc())
            .all()
        )

    return {
        "patient_id": patient.id,
        "labs": [
            {
                "id": row.id,
                "item_name": row.item_name,
                "result": row.result,
                "reported_at": row.reported_at,
            }
            for row in labs
        ],
        "imaging": [
            {
                "id": row.id,
                "item_name": row.item_name,
                "report": row.report,
                "image_url": row.image_url,
                "reported_at": row.reported_at,
            }
            for row in imaging
        ],
    }
