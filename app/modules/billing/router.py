from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.modules.auth.security import require_role

from .schemas import BillingSummary, PaymentCreate, PaymentResponse
from .service import create_payment, get_payment, get_summary, list_payments, refund_payment

router = APIRouter(prefix="/payments", tags=["payments"])


@router.post("/", response_model=PaymentResponse, status_code=201)
def pay(
    data: PaymentCreate,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("cashier")),
):
    try:
        return create_payment(db, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/", response_model=list[PaymentResponse])
def get_all(
    status: str | None = None,
    encounter_id: int | None = None,
    db: Session = Depends(get_db),
):
    return list_payments(db, status, encounter_id)


@router.get("/summary", response_model=BillingSummary)
def summary(db: Session = Depends(get_db)):
    return get_summary(db)


@router.post("/{payment_id}/refund", response_model=PaymentResponse)
def refund(
    payment_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("cashier")),
):
    try:
        return refund_payment(db, payment_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{payment_id}", response_model=PaymentResponse)
def get_one(payment_id: int, db: Session = Depends(get_db)):
    payment = get_payment(db, payment_id)
    if not payment:
        raise HTTPException(status_code=404, detail="收费记录不存在")
    return payment
