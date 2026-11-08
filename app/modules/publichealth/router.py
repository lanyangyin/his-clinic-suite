from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.modules.auth.security import require_role

from .schemas import ReportCreate, ReportResponse
from .service import create_report, get_report, list_reports, submit_report

router = APIRouter(prefix="/public-health", tags=["public-health"])


@router.post("/reports", response_model=ReportResponse, status_code=201)
def new_report(
    data: ReportCreate,
    db: Session = Depends(get_db),
    user=Depends(require_role("doctor")),
):
    try:
        return create_report(db, data, user.username)
    except ValueError as e:
        code = 404 if str(e) == "就诊记录不存在" else 400
        raise HTTPException(status_code=code, detail=str(e))


@router.get("/reports", response_model=list[ReportResponse])
def get_all(status: str | None = None, db: Session = Depends(get_db)):
    return list_reports(db, status)


@router.get("/reports/{report_id}", response_model=ReportResponse)
def get_one(report_id: int, db: Session = Depends(get_db)):
    report = get_report(db, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="报告卡不存在")
    return report


@router.post("/reports/{report_id}/submit", response_model=ReportResponse)
def submit(
    report_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("admin")),
):
    try:
        return submit_report(db, report_id)
    except ValueError as e:
        code = 404 if str(e) == "报告卡不存在" else 400
        raise HTTPException(status_code=code, detail=str(e))
