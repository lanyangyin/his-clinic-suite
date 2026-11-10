from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.modules.auth.security import require_role

from .schemas import ShiftClose, ShiftOpen, ShiftResponse
from .service import close_shift, daily, list_shifts, open_shift

router = APIRouter(prefix="/cashier", tags=["cashier"])


@router.get("/daily")
def get_daily(
    day: date | None = None,
    db: Session = Depends(get_db),
    user=Depends(require_role("cashier", "admin")),
):
    cashier = user.username if user.role == "cashier" else None
    return daily(db, day, cashier)


@router.get("/shifts", response_model=list[ShiftResponse])
def get_shifts(
    day: date | None = None,
    db: Session = Depends(get_db),
    user=Depends(require_role("cashier", "admin")),
):
    cashier = user.username if user.role == "cashier" else None
    return list_shifts(db, day, cashier)


@router.post("/shifts/open", response_model=ShiftResponse, status_code=201)
def open_new(
    data: ShiftOpen,
    db: Session = Depends(get_db),
    user=Depends(require_role("cashier")),
):
    try:
        return open_shift(db, user.username, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/shifts/{shift_id}/close", response_model=ShiftResponse)
def close(
    shift_id: int,
    data: ShiftClose,
    db: Session = Depends(get_db),
    user=Depends(require_role("cashier")),
):
    try:
        return close_shift(db, shift_id, user.username, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
