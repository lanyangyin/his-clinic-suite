from sqlalchemy.orm import Session

from app.modules.billing.models import Payment
from app.modules.billing.schemas import PaymentCreate
from app.modules.billing.service import create_payment
from app.modules.patient.service import get_patient_by_id_number
from app.modules.registration.models import Registration
from app.modules.registration.schemas import RegistrationCreate
from app.modules.registration.service import create_registration


def kiosk_registration(
    db: Session, patient_id_number: str, doctor_id: int, schedule_id: int | None = None
) -> Registration:
    """自助挂号：患者须已建档，其余复用挂号服务（医生校验、号源占用）。"""
    patient = get_patient_by_id_number(db, patient_id_number)
    if not patient:
        raise ValueError("患者未建档，请先到建档窗口办理")

    return create_registration(
        db,
        RegistrationCreate(
            patient_id=patient.id, doctor_id=doctor_id, schedule_id=schedule_id
        ),
    )


def kiosk_payment(db: Session, encounter_id: int) -> Payment:
    """自助缴费：复用收费服务（金额计算、医保结算、就诊关闭）。"""
    return create_payment(db, PaymentCreate(encounter_id=encounter_id))
