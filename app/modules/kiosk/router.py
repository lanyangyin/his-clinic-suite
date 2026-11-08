from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.modules.registration.service import get_registration

from .schemas import (
    KioskPaymentCreate,
    KioskPaymentResponse,
    KioskRegistrationCreate,
    KioskRegistrationResponse,
)
from .service import kiosk_payment, kiosk_registration

router = APIRouter(prefix="/kiosk", tags=["kiosk"])


@router.post(
    "/registrations",
    response_model=KioskRegistrationResponse,
    status_code=201,
)
def self_service_registration(
    data: KioskRegistrationCreate, db: Session = Depends(get_db)
):
    """自助机挂号（开放接口：生产环境应加终端鉴权与限流）。"""
    try:
        return kiosk_registration(db, data.patient_id_number, data.doctor_id, data.schedule_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "/registrations/{registration_id}", response_model=KioskRegistrationResponse
)
def get_kiosk_registration(registration_id: int, db: Session = Depends(get_db)):
    registration = get_registration(db, registration_id)
    if not registration:
        raise HTTPException(status_code=404, detail="挂号记录不存在")
    return registration


@router.post("/payments", response_model=KioskPaymentResponse, status_code=201)
def self_service_payment(data: KioskPaymentCreate, db: Session = Depends(get_db)):
    """自助缴费（开放接口：生产环境应加终端鉴权与限流）。"""
    try:
        return kiosk_payment(db, data.encounter_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
