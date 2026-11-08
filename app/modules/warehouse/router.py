from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.modules.auth.security import require_role

from .schemas import (
    CheckCreate,
    CheckResponse,
    OutboundOrderCreate,
    OutboundOrderResponse,
    PurchaseCreate,
    PurchaseRecordResponse,
    TransferCreate,
    TransferResponse,
    WarehouseStockResponse,
)
from .service import (
    approve_outbound,
    cancel_outbound,
    check,
    create_outbound,
    get_outbound,
    issue_outbound,
    list_checks,
    list_outbounds,
    list_purchases,
    list_stocks,
    purchase,
    transfer,
)

router = APIRouter(prefix="/warehouse", tags=["warehouse"])


@router.post("/purchase", response_model=WarehouseStockResponse, status_code=201)
def purchase_stock(
    data: PurchaseCreate,
    db: Session = Depends(get_db),
    user=Depends(require_role("admin")),
):
    try:
        return purchase(db, data, user.username)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/purchases", response_model=list[PurchaseRecordResponse])
def get_purchases(
    drug_id: int | None = None,
    supplier_id: int | None = None,
    db: Session = Depends(get_db),
):
    return list_purchases(db, drug_id, supplier_id)


@router.get("/stocks", response_model=list[WarehouseStockResponse])
def get_stocks(drug_id: int | None = None, db: Session = Depends(get_db)):
    return list_stocks(db, drug_id)


@router.post("/transfer", response_model=TransferResponse)
def transfer_stock(
    data: TransferCreate,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("pharmacist")),
):
    try:
        return transfer(db, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/check", response_model=CheckResponse)
def check_stock(
    data: CheckCreate,
    db: Session = Depends(get_db),
    user=Depends(require_role("pharmacist")),
):
    try:
        return check(db, data, user.username)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/checks", response_model=list[CheckResponse])
def get_checks(drug_id: int | None = None, db: Session = Depends(get_db)):
    return list_checks(db, drug_id)


# ---------- 出库单（药房/科室领用）----------
@router.post("/outbound-orders", response_model=OutboundOrderResponse, status_code=201)
def new_outbound(
    data: OutboundOrderCreate,
    db: Session = Depends(get_db),
    user=Depends(require_role("pharmacist")),
):
    """药房/科室提交领用申请（库房出库单）。"""
    try:
        return create_outbound(db, data, applicant=user.username)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/outbound-orders", response_model=list[OutboundOrderResponse])
def get_outbounds(
    status: str | None = None,
    target_type: str | None = None,
    db: Session = Depends(get_db),
):
    return list_outbounds(db, status, target_type)


@router.get("/outbound-orders/{order_id}", response_model=OutboundOrderResponse)
def get_outbound_one(order_id: int, db: Session = Depends(get_db)):
    order = get_outbound(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="出库单不存在")
    return order


@router.post("/outbound-orders/{order_id}/approve", response_model=OutboundOrderResponse)
def approve(
    order_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_role("pharmacist")),
):
    """库房审核出库申请。"""
    try:
        return approve_outbound(db, order_id, approver=user.username)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/outbound-orders/{order_id}/issue", response_model=OutboundOrderResponse)
def issue(
    order_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_role("pharmacist")),
):
    """库房出库：扣总库、增药房/科室库存。"""
    try:
        return issue_outbound(db, order_id, issuer=user.username)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/outbound-orders/{order_id}/cancel", response_model=OutboundOrderResponse)
def cancel(
    order_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("pharmacist")),
):
    try:
        return cancel_outbound(db, order_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
