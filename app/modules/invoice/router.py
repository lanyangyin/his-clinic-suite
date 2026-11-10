from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.modules.auth.security import require_role

from .schemas import InvoiceBatchCreate, InvoiceBatchResponse
from .service import close_batch, create_batch, list_batches

router = APIRouter(prefix="/invoices", tags=["invoices"])


@router.post("/batches", response_model=InvoiceBatchResponse, status_code=201)
def new_batch(
    data: InvoiceBatchCreate,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("admin")),
):
    try:
        return create_batch(db, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/batches", response_model=list[InvoiceBatchResponse])
def get_batches(
    status: str | None = None,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("admin")),
):
    return list_batches(db, status)


@router.post("/batches/{batch_id}/close", response_model=InvoiceBatchResponse)
def close(
    batch_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("admin")),
):
    try:
        return close_batch(db, batch_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
