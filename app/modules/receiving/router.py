from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.modules.auth.security import require_role

from .schemas import InboundCheckRequest, InboundOrderCreate, InboundOrderResponse
from .service import (
    cancel_order,
    check_order,
    create_order,
    get_order,
    list_orders,
    stock_order,
)

router = APIRouter(prefix="/inbound", tags=["receiving"])


@router.post("/orders", response_model=InboundOrderResponse, status_code=201)
def new_order(
    data: InboundOrderCreate,
    db: Session = Depends(get_db),
    user=Depends(require_role("warehouse")),
):
    """创建入库单（收货）：药品需批号/效期，器械需注册证。"""
    try:
        return create_order(db, data, received_by=user.username)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/orders", response_model=list[InboundOrderResponse])
def get_orders(
    status: str | None = None,
    order_type: str | None = None,
    db: Session = Depends(get_db),
):
    return list_orders(db, status, order_type)


@router.get("/orders/{order_id}", response_model=InboundOrderResponse)
def get_one(order_id: int, db: Session = Depends(get_db)):
    order = get_order(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="入库单不存在")
    return order


@router.post("/orders/{order_id}/check", response_model=InboundOrderResponse)
def check(
    order_id: int,
    data: InboundCheckRequest,
    db: Session = Depends(get_db),
    user=Depends(require_role("warehouse")),
):
    """验收：登记不合格数量/原因。"""
    try:
        return check_order(db, order_id, data, checked_by=user.username)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/orders/{order_id}/stock", response_model=InboundOrderResponse)
def stock(
    order_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("warehouse")),
):
    """入库：合格数量写入库存。"""
    try:
        return stock_order(db, order_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/orders/{order_id}/cancel", response_model=InboundOrderResponse)
def cancel(
    order_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("warehouse")),
):
    try:
        return cancel_order(db, order_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

