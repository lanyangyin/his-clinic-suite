from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.modules.auth.security import require_role

from .schemas import (
    CheckCreate,
    CheckResponse,
    PurchaseCreate,
    PurchaseRecordResponse,
    TransferCreate,
    TransferResponse,
    WarehouseStockResponse,
)
from .service import (
    check,
    list_checks,
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
