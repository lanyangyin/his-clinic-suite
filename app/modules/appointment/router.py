from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.modules.auth.security import require_role

from .schemas import AppointmentCreate, AppointmentResponse
from .service import (
    cancel,
    check_in,
    create_appointment,
    get_appointment,
    list_appointments,
    no_show,
)

router = APIRouter(prefix="/appointments", tags=["appointments"])


@router.post("/", response_model=AppointmentResponse, status_code=201)
def new_appointment(
    data: AppointmentCreate,
    db: Session = Depends(get_db),
    user=Depends(require_role("cashier")),
):
    try:
        return create_appointment(db, data, created_by=user.username)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/", response_model=list[AppointmentResponse])
def get_all(
    patient_id: int | None = None,
    doctor_id: int | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
):
    return list_appointments(db, patient_id, doctor_id, status)


@router.get("/{appointment_id}", response_model=AppointmentResponse)
def get_one(appointment_id: int, db: Session = Depends(get_db)):
    appointment = get_appointment(db, appointment_id)
    if not appointment:
        raise HTTPException(status_code=404, detail="预约不存在")
    return appointment


@router.post("/{appointment_id}/check-in", response_model=AppointmentResponse)
def check_in_appointment(
    appointment_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("cashier")),
):
    try:
        return check_in(db, appointment_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{appointment_id}/no-show", response_model=AppointmentResponse)
def mark_no_show(
    appointment_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("cashier")),
):
    try:
        return no_show(db, appointment_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{appointment_id}/cancel", response_model=AppointmentResponse)
def cancel_appointment(
    appointment_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("cashier")),
):
    try:
        return cancel(db, appointment_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
