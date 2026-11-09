from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.modules.auth.security import require_role

from .schemas import (
    CurtainCreate,
    CurtainResponse,
    DistributionCreate,
    DistributionResponse,
    LinenBatchCreate,
    LinenBatchResponse,
    LinenSummary,
    RecallCreate,
)
from .service import (
    create_batch,
    create_curtain,
    curtain_reminders,
    distribute,
    get_batch,
    list_batches,
    list_curtains,
    recall,
    summary,
)

router = APIRouter(prefix="/linen", tags=["linen"])


@router.post("/batches", response_model=LinenBatchResponse, status_code=201)
def new_batch(
    data: LinenBatchCreate,
    db: Session = Depends(get_db),
    user=Depends(require_role("nurse", "warehouse")),
):
    try:
        return create_batch(db, data, user.username)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/batches", response_model=list[LinenBatchResponse])
def batches(
    category: str | None = None,
    status: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("nurse", "warehouse")),
):
    return list_batches(db, category, status, start_date, end_date)


@router.get("/batches/{batch_id}", response_model=LinenBatchResponse)
def batch_detail(
    batch_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("nurse", "warehouse")),
):
    batch = get_batch(db, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="被服批次不存在")
    return batch


@router.post("/batches/{batch_id}/distribute", response_model=DistributionResponse, status_code=201)
def distribute_batch(
    batch_id: int,
    data: DistributionCreate,
    db: Session = Depends(get_db),
    user=Depends(require_role("nurse", "warehouse")),
):
    try:
        return distribute(db, batch_id, data, user.username)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/batches/{batch_id}/recall", response_model=LinenBatchResponse)
def recall_batch(
    batch_id: int,
    data: RecallCreate,
    db: Session = Depends(get_db),
    user=Depends(require_role("nurse", "warehouse")),
):
    try:
        return recall(db, batch_id, data.reason, user.username)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/curtains", response_model=CurtainResponse, status_code=201)
def new_curtain(
    data: CurtainCreate,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("nurse", "warehouse")),
):
    return create_curtain(db, data)


@router.get("/curtains", response_model=list[CurtainResponse])
def curtains(
    department: str | None = None,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("nurse", "warehouse")),
):
    return list_curtains(db, department)


@router.get("/curtains/reminders", response_model=list[CurtainResponse])
def curtain_due(
    days: int = 30,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("nurse", "warehouse")),
):
    return curtain_reminders(db, days)


@router.get("/summary", response_model=LinenSummary)
def linen_summary(
    start_date: date,
    end_date: date,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("nurse", "warehouse")),
):
    return summary(db, start_date, end_date)
