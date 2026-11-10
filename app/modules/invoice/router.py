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

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.modules.auth.security import require_role

from .schemas import InvoicePrintResponse, InvoiceVoid
from .service_ops import operations, print_invoice, usage, void_invoice


@router.post("/payments/{payment_id}/print")
def print_invoice_route(
    payment_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_role("cashier", "admin")),
):
    try:
        payment = print_invoice(db, payment_id, user.username, user.role == "admin")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {
        "payment_id": payment.id,
        "invoice_no": payment.invoice_no,
        "invoice_status": payment.invoice_status,
        "print_count": payment.invoice_print_count,
    }


@router.post("/payments/{payment_id}/void")
def void_invoice_route(
    payment_id: int,
    data: InvoiceVoid,
    db: Session = Depends(get_db),
    user=Depends(require_role("cashier", "admin")),
):
    try:
        payment = void_invoice(
            db, payment_id, data.reason, user.username, user.role == "admin"
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {
        "payment_id": payment.id,
        "invoice_no": payment.invoice_no,
        "invoice_status": payment.invoice_status,
        "void_reason": payment.invoice_void_reason,
    }


@router.get("/usage")
def invoice_usage(
    start_date: date | None = None,
    end_date: date | None = None,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("admin")),
):
    return usage(db, start_date, end_date)


@router.get("/payments/{payment_id}/operations")
def invoice_operations(
    payment_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("admin")),
):
    return [
        {
            "action": row.action,
            "operator": row.operator,
            "reason": row.reason,
            "created_at": row.created_at,
        }
        for row in operations(db, payment_id)
    ]
