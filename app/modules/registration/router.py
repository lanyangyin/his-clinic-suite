from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.modules.auth.security import require_role
from app.modules.staff.service import get_doctor

from .schemas import RegistrationCreate, RegistrationResponse, ScheduleCreate, ScheduleResponse
from .service import (
    create_registration,
    create_schedule,
    get_registration,
    get_schedule,
    list_registrations,
    list_schedules,
)

router = APIRouter(prefix="/registrations", tags=["registrations"])
schedule_router = APIRouter(tags=["schedules"])

_NOT_FOUND_MESSAGES = {"患者不存在", "医生不存在", "排班不存在"}


@router.post("/", response_model=RegistrationResponse, status_code=201)
def register(
    data: RegistrationCreate,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("cashier")),
):
    try:
        return create_registration(db, data)
    except ValueError as e:
        code = 404 if str(e) in _NOT_FOUND_MESSAGES else 400
        raise HTTPException(status_code=code, detail=str(e))


@router.get("/", response_model=list[RegistrationResponse])
def get_all(
    patient_id: int | None = None,
    doctor_id: int | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
):
    return list_registrations(db, patient_id, doctor_id, status)


@router.get("/{registration_id}", response_model=RegistrationResponse)
def get_one(registration_id: int, db: Session = Depends(get_db)):
    registration = get_registration(db, registration_id)
    if not registration:
        raise HTTPException(status_code=404, detail="挂号记录不存在")
    return registration


@schedule_router.post("/schedules/", response_model=ScheduleResponse, status_code=201)
def new_schedule(
    data: ScheduleCreate,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("admin")),
):
    try:
        return create_schedule(db, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@schedule_router.get("/schedules/{schedule_id}", response_model=ScheduleResponse)
def get_schedule_one(schedule_id: int, db: Session = Depends(get_db)):
    schedule = get_schedule(db, schedule_id)
    if not schedule:
        raise HTTPException(status_code=404, detail="排班不存在")
    return schedule


@schedule_router.get(
    "/doctors/{doctor_id}/schedules", response_model=list[ScheduleResponse]
)
def get_doctor_schedules(
    doctor_id: int,
    schedule_date: date | None = None,
    db: Session = Depends(get_db),
):
    if not get_doctor(db, doctor_id):
        raise HTTPException(status_code=404, detail="医生不存在")
    return list_schedules(db, doctor_id, schedule_date)
