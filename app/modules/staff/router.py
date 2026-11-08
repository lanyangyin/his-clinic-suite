from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.modules.auth.security import require_role

from .schemas import (
    DepartmentCreate,
    DepartmentResponse,
    DoctorCreate,
    DoctorResponse,
)
from .service import create_department, create_doctor, get_department, get_doctor, list_doctors

router = APIRouter(tags=["staff"])


@router.get("/doctors/", response_model=list[DoctorResponse])
def get_all_doctors(department_id: int | None = None, db: Session = Depends(get_db)):
    return list_doctors(db, department_id)


@router.post("/departments/", response_model=DepartmentResponse, status_code=201)
def new_department(
    data: DepartmentCreate,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("admin")),
):
    return create_department(db, data)


@router.get("/departments/{department_id}", response_model=DepartmentResponse)
def get_department_one(department_id: int, db: Session = Depends(get_db)):
    department = get_department(db, department_id)
    if not department:
        raise HTTPException(status_code=404, detail="科室不存在")
    return department


@router.post("/doctors/", response_model=DoctorResponse, status_code=201)
def new_doctor(
    data: DoctorCreate,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("admin")),
):
    try:
        return create_doctor(db, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/doctors/{doctor_id}", response_model=DoctorResponse)
def get_doctor_one(doctor_id: int, db: Session = Depends(get_db)):
    doctor = get_doctor(db, doctor_id)
    if not doctor:
        raise HTTPException(status_code=404, detail="医生不存在")
    return doctor
