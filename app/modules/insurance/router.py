from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.modules.auth.security import require_role

from .workbench import encounter_risks, workbench

router = APIRouter(prefix="/insurance", tags=["insurance"])


@router.get("/workbench")
def get_workbench(
    start_date: date | None = None,
    end_date: date | None = None,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("admin")),
):
    return workbench(db, start_date, end_date)


@router.get("/risks/encounter/{encounter_id}")
def get_encounter_risks(
    encounter_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("doctor", "admin")),
):
    data = encounter_risks(db, encounter_id)
    if not data:
        raise HTTPException(status_code=404, detail="就诊记录不存在")
    return data
