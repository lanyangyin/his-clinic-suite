from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.modules.auth.security import require_role

from .schemas import ClosureResponse, DailyCloseRequest, MonthlySummaryResponse
from .service import daily_close, get_closure, list_closures, monthly_summary

router = APIRouter(prefix="/finance", tags=["finance"])


@router.post("/daily-close", response_model=ClosureResponse, status_code=201)
def close_day(
    data: DailyCloseRequest,
    db: Session = Depends(get_db),
    user=Depends(require_role("admin")),
):
    try:
        return daily_close(db, data, user.username)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/daily-closes", response_model=list[ClosureResponse])
def get_closures(db: Session = Depends(get_db)):
    return list_closures(db)


@router.get("/daily-close/{close_date}", response_model=ClosureResponse)
def get_one(close_date: date, db: Session = Depends(get_db)):
    closure = get_closure(db, close_date)
    if not closure:
        raise HTTPException(status_code=404, detail="该日未日结")
    return closure


@router.get("/monthly-summary", response_model=MonthlySummaryResponse)
def get_monthly(month: str, db: Session = Depends(get_db)):
    try:
        return monthly_summary(db, month)
    except (ValueError, IndexError):
        raise HTTPException(status_code=400, detail="月份格式应为 YYYY-MM")
