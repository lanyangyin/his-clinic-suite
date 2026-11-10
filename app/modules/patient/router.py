from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.modules.auth.security import require_role

from .history import get_patient_history
from .profile import patient_profile
from .schemas import (
    DuplicateCheckResponse,
    PatientCreate,
    PatientResponse,
    PatientUpdate,
)
from .service import (
    create_patient,
    find_duplicates,
    get_patient,
    list_patients,
    update_patient,
)

router = APIRouter(prefix="/patients", tags=["patients"])


@router.post("/", response_model=PatientResponse, status_code=201)
def register_patient(
    data: PatientCreate,
    db: Session = Depends(get_db),
    user=Depends(require_role("cashier")),
):
    return create_patient(db, data, user.username)


@router.get("/duplicates", response_model=DuplicateCheckResponse)
def check_duplicates(
    name: str = "",
    id_number: str = "",
    phone: str = "",
    db: Session = Depends(get_db),
    _: None = Depends(require_role("cashier")),
):
    exact, candidates = find_duplicates(db, name, id_number, phone)
    return {"exact": exact, "candidates": candidates}


@router.get("/", response_model=list[PatientResponse])
def get_all(
    name: str | None = None,
    id_number: str | None = None,
    phone: str | None = None,
    db: Session = Depends(get_db),
):
    return list_patients(db, name, id_number, phone)


@router.put("/{patient_id}", response_model=PatientResponse)
def update_one(
    patient_id: int,
    data: PatientUpdate,
    db: Session = Depends(get_db),
    user=Depends(require_role("cashier")),
):
    try:
        patient = update_patient(db, patient_id, data, user.username)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    if not patient:
        raise HTTPException(status_code=404, detail="患者不存在")
    return patient


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
