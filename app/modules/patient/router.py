from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.modules.auth.security import require_role
from .schemas import PatientCreate, PatientResponse
from .service import create_patient, get_patient, list_patients
from .history import get_patient_history
from .profile import patient_profile

router = APIRouter(prefix="/patients", tags=["patients"])

@router.post("/", response_model=PatientResponse, status_code=201)
def register_patient(
    data: PatientCreate,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("cashier")),
):
    return create_patient(db, data)


@router.get("/", response_model=list[PatientResponse])
def get_all(
    name: str | None = None,
    id_number: str | None = None,
    db: Session = Depends(get_db),
):
    return list_patients(db, name, id_number)


@router.get("/{patient_id}", response_model=PatientResponse)
def get_one(patient_id: int, db: Session = Depends(get_db)):
    patient = get_patient(db, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="患者不存在")
    return patient


@router.get("/{patient_id}/history")
def get_history(
    patient_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("doctor", "admin")),
):
    """医生查看患者历史诊疗：历次病历、处方、检验、治疗、收费一次返回。"""
    history = get_patient_history(db, patient_id)
    if not history:
        raise HTTPException(status_code=404, detail="患者不存在")
    return history
@router.get("/{patient_id}/profile")
def get_profile(
    patient_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("doctor", "admin")),
):
    """患者 360：基本信息、就诊时间线、预约、病案、费用统计。"""
    data = patient_profile(db, patient_id)
    if not data:
        raise HTTPException(status_code=404, detail="患者不存在")
    return data
