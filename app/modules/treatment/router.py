from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.modules.auth.security import require_role

from .schemas import TreatmentOrderCreate, TreatmentOrderResponse
from .service import (
    cancel_treatment,
    create_treatment,
    execute_treatment,
    get_treatment,
    list_all_treatments,
    list_treatments,
)

router = APIRouter(prefix="/treatments", tags=["treatments"])


@router.get("/", response_model=list[TreatmentOrderResponse])
def get_all(status: str | None = None, db: Session = Depends(get_db)):
    """治疗单列表（可按状态过滤，最新在前）。"""
    return list_all_treatments(db, status)


@router.post(
    "/encounters/{encounter_id}",
    response_model=TreatmentOrderResponse,
    status_code=201,
)
def new_treatment(
    encounter_id: int,
    data: TreatmentOrderCreate,
    db: Session = Depends(get_db),
    user=Depends(require_role("doctor")),
):
    try:
        return create_treatment(db, encounter_id, data, ordered_by=user.username)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "/encounters/{encounter_id}", response_model=list[TreatmentOrderResponse]
)
def get_encounter_treatments(encounter_id: int, db: Session = Depends(get_db)):
    return list_treatments(db, encounter_id)


@router.get("/{order_id}", response_model=TreatmentOrderResponse)
def get_one(order_id: int, db: Session = Depends(get_db)):
    order = get_treatment(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="治疗单不存在")
    return order


@router.post("/{order_id}/execute", response_model=TreatmentOrderResponse)
def execute(
    order_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_role("nurse")),
):
    try:
        return execute_treatment(db, order_id, executed_by=user.username)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{order_id}/cancel", response_model=TreatmentOrderResponse)
def cancel(
    order_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("doctor")),
):
    try:
        return cancel_treatment(db, order_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
