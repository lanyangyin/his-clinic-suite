from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.modules.auth.security import require_read_login, require_role

from .schemas import BillingSummary, PaymentCreate, PaymentResponse, RefundRequest
from .service import (
    create_payment, get_payment, get_summary, list_payments,
    list_pending_encounters, refund_payment,
)
from .models import RefundApproval

router = APIRouter(prefix="/payments", tags=["payments"], dependencies=[Depends(require_read_login)])


@router.post("/", response_model=PaymentResponse, status_code=201)
def pay(
    data: PaymentCreate,
    db: Session = Depends(get_db),
    user=Depends(require_role("cashier", "doctor", "pharmacist", "admin", "director")),
):
    try:
        return create_payment(
            db, data, created_by=user.username,
            allow_discount=user.role in ("admin", "director"),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/", response_model=list[PaymentResponse])
def get_all(
    status: str | None = None,
    encounter_id: int | None = None,
    db: Session = Depends(get_db),
):
    return list_payments(db, status, encounter_id)


@router.get("/pending-encounters")
def pending_encounters(
    limit: int = 100,
    db: Session = Depends(get_db),
    _=Depends(require_role("cashier", "doctor", "admin")),
):
    return list_pending_encounters(db, max(1, min(limit, 500)))


@router.get("/summary", response_model=BillingSummary)
def summary(db: Session = Depends(get_db)):
    return get_summary(db)


@router.post("/{payment_id}/refund", response_model=PaymentResponse)
def refund(
    payment_id: int,
    data: RefundRequest | None = None,
    db: Session = Depends(get_db),
    user=Depends(require_role("cashier", "admin", "director")),
):
    try:
        return refund_payment(
            db,
            payment_id,
            items=data.items if data else None,
            operator=user.username,
            reason=data.reason if data else "",
            operator_role=user.role,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{payment_id}/refund-approvals")
def refund_approvals(
    payment_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("cashier", "admin", "director")),
):
    rows = (
        db.query(RefundApproval)
        .filter(RefundApproval.payment_id == payment_id)
        .order_by(RefundApproval.id.desc())
        .all()
    )
    return [
        {
            "id": row.id,
            "refund_no": row.refund_no,
            "amount": row.amount,
            "reason": row.reason,
            "operator": row.operator,
            "operator_role": row.operator_role,
            "created_at": row.created_at,
        }
        for row in rows
    ]


@router.get("/{payment_id}", response_model=PaymentResponse)
def get_one(payment_id: int, db: Session = Depends(get_db)):
    payment = get_payment(db, payment_id)
    if not payment:
        raise HTTPException(status_code=404, detail="收费记录不存在")
    return payment
