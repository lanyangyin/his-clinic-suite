from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.modules.auth.security import require_role

from .schemas import StocktakeCounts, StocktakeCreate, StocktakeResponse
from .service import (
    cancel_stocktake,
    complete_stocktake,
    create_stocktake,
    get_stocktake,
    list_stocktakes,
    save_counts,
)

router = APIRouter(prefix="/stocktakes", tags=["stocktakes"])


@router.post("", response_model=StocktakeResponse, status_code=201)
def new_stocktake(
    data: StocktakeCreate,
    db: Session = Depends(get_db),
    user=Depends(require_role("warehouse", "pharmacist")),
):
    try:
        return create_stocktake(db, data, user.username)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("", response_model=list[StocktakeResponse])
def get_stocktakes(
    status: str | None = None,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("warehouse", "pharmacist")),
):
    return list_stocktakes(db, status)


@router.get("/{take_id}", response_model=StocktakeResponse)
def get_one(
    take_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("warehouse", "pharmacist")),
):
    take = get_stocktake(db, take_id)
    if not take:
        raise HTTPException(status_code=404, detail="盘点单不存在")
    return take


@router.put("/{take_id}/counts", response_model=StocktakeResponse)
def update_counts(
    take_id: int,
    data: StocktakeCounts,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("warehouse", "pharmacist")),
):
    try:
        return save_counts(db, take_id, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{take_id}/complete", response_model=StocktakeResponse)
def complete(
    take_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_role("warehouse", "pharmacist")),
):
    try:
        return complete_stocktake(db, take_id, user.username)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{take_id}/cancel", response_model=StocktakeResponse)
def cancel(
    take_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("warehouse", "pharmacist")),
):
    try:
        return cancel_stocktake(db, take_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
