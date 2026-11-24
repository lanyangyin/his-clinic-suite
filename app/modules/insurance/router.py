from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.modules.auth.security import require_read_login, require_role

from .models import InsuranceTransaction
from .workbench import encounter_risks, workbench

router = APIRouter(prefix="/insurance", tags=["insurance"], dependencies=[Depends(require_read_login)])


@router.get("/workbench")
def get_workbench(
    start_date: date | None = None,
    end_date: date | None = None,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("admin")),
):
    return workbench(db, start_date, end_date)


@router.get("/transactions")
def get_transactions(
    encounter_id: int | None = None,
    limit: int = 100,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("doctor", "admin")),
):
    query = db.query(InsuranceTransaction)
    if encounter_id is not None:
        query = query.filter(InsuranceTransaction.encounter_id == encounter_id)
    rows = query.order_by(InsuranceTransaction.id.desc()).limit(min(max(limit, 1), 500)).all()
    return [
        {
            "id": row.id,
            "encounter_id": row.encounter_id,
            "kind": row.kind,
            "drug_name": row.drug_name,
            "quantity": row.quantity,
            "ratio": row.ratio,
            "result": row.result,
            "message": row.message,
            "settlement_no": row.settlement_no,
            "operator": row.operator,
            "created_at": row.created_at,
        }
        for row in rows
    ]


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
