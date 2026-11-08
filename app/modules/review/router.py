from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.modules.auth.security import require_role

from .schemas import ReviewDetail, ReviewIssue, ReviewSummary
from .service import detail, issues, summary

router = APIRouter(prefix="/review", tags=["review"])


@router.get("/summary", response_model=ReviewSummary)
def get_summary(
    start_date: date | None = None,
    end_date: date | None = None,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("admin", "pharmacist")),
):
    """处方点评汇总（按就诊创建时间过滤）。"""
    return summary(db, start_date, end_date)


@router.get("/issues", response_model=list[ReviewIssue])
def get_issues(
    start_date: date | None = None,
    end_date: date | None = None,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("admin", "pharmacist")),
):
    """可疑处方明细（医保超量提醒/单次超量）。"""
    return issues(db, start_date, end_date)


@router.get("/encounters/{encounter_id}", response_model=ReviewDetail)
def get_detail(
    encounter_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("admin", "pharmacist")),
):
    try:
        return detail(db, encounter_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
