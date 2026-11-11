from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.modules.auth.security import require_role

from .history import get_patient_history
from .profile import patient_profile
from .schemas import (
    ClinicalChangeResponse,
    ClinicalProfileUpdate,
    DuplicateCheckResponse,
    PatientCardCreate,
    PatientCardResponse,
    PatientCreate,
    PatientResponse,
    PatientUpdate,
)
from .service import (
    list_clinical_changes,
    update_clinical_profile,
    create_patient,
    find_by_card,
    find_duplicates,
    get_patient,
    issue_card,
    list_cards,
    list_patients,
    mark_card_lost,
    reissue_card,
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


@router.put("/{patient_id}/clinical-profile", response_model=PatientResponse)
def update_clinical(
    patient_id: int,
    data: ClinicalProfileUpdate,
    db: Session = Depends(get_db),
    user=Depends(require_role("doctor", "admin")),
):
    try:
        return update_clinical_profile(db, patient_id, data, user.username)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get(
    "/{patient_id}/clinical-changes",
    response_model=list[ClinicalChangeResponse],
)
def clinical_changes(
    patient_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("doctor", "admin")),
):
    return list_clinical_changes(db, patient_id)


@router.get("/by-card/{card_uid}")
def get_by_card(card_uid: str, db: Session = Depends(get_db)):
    """NFC 刷卡查患者：只返回正常状态的卡。"""
    found = find_by_card(db, card_uid)
    if not found:
        raise HTTPException(status_code=404, detail="未找到有效就诊卡")
    patient = found["patient"]
    return {
        "card": found["card"],
        "patient": PatientResponse.model_validate(patient).model_dump(),
    }


@router.post("/{patient_id}/cards", response_model=PatientCardResponse, status_code=201)
def create_card(
    patient_id: int,
    data: PatientCardCreate,
    db: Session = Depends(get_db),
    user=Depends(require_role("cashier")),
):
    try:
        return issue_card(db, patient_id, data.card_uid, user.username, data.note)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/{patient_id}/cards", response_model=list[PatientCardResponse])
def cards(patient_id: int, db: Session = Depends(get_db)):
    try:
        return list_cards(db, patient_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/{patient_id}/cards/{card_id}/lost", response_model=PatientCardResponse)
def lost_card(
    patient_id: int,
    card_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_role("cashier")),
):
    try:
        return mark_card_lost(db, patient_id, card_id, user.username)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/{patient_id}/cards/reissue", response_model=PatientCardResponse, status_code=201)
def reissue(
    patient_id: int,
    data: PatientCardCreate,
    db: Session = Depends(get_db),
    user=Depends(require_role("cashier")),
):
    try:
        return reissue_card(db, patient_id, data.card_uid, user.username, data.note)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


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
