from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.modules.auth.security import require_role

from .schemas import OverviewResponse, RevenueTrendItem, TopDiagnosisItem, TopDrugItem
from .service import overview, revenue_trend, top_diagnoses, top_drugs

router = APIRouter(prefix="/bi", tags=["bi"])


@router.get("/overview", response_model=OverviewResponse)
def get_overview(
    db: Session = Depends(get_db), _: None = Depends(require_role("admin"))
):
    return overview(db)


@router.get("/revenue-trend", response_model=list[RevenueTrendItem])
def get_revenue_trend(
    days: int = 7,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("admin")),
):
    days = max(1, min(days, 90))
    return revenue_trend(db, days)


@router.get("/top-diagnoses", response_model=list[TopDiagnosisItem])
def get_top_diagnoses(
    limit: int = 5,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("admin")),
):
    return top_diagnoses(db, max(1, min(limit, 50)))


@router.get("/top-drugs", response_model=list[TopDrugItem])
def get_top_drugs(
    limit: int = 5,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("admin")),
):
    return top_drugs(db, max(1, min(limit, 50)))
