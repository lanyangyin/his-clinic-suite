from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.modules.auth.security import require_role

from .schemas import (
    DispenseRequest,
    DispenseResponse,
    StockInRequest,
    StockInResponse,
    StockResponse,
)
from .service import dispense, get_dispense, get_stock, list_stocks, return_dispense, stock_in

router = APIRouter(prefix="/pharmacy", tags=["pharmacy"])


@router.post("/dispense", response_model=DispenseResponse, status_code=201)
def dispense_medicines(
    data: DispenseRequest,
    db: Session = Depends(get_db),
    user=Depends(require_role("pharmacist")),
):
    try:
        return dispense(db, data, operator=user.username)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/dispense/{dispense_id}/return", response_model=DispenseResponse)
def return_medicines(
    dispense_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_role("pharmacist")),
):
    """门诊退药：库存回补；退药后可继续退费。"""
    try:
        return return_dispense(db, dispense_id, operator=user.username)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/dispense/{dispense_id}", response_model=DispenseResponse)
def get_one(dispense_id: int, db: Session = Depends(get_db)):
    record = get_dispense(db, dispense_id)
    if not record:
        raise HTTPException(status_code=404, detail="发药记录不存在")
    return record


@router.post("/stock-in", response_model=StockInResponse, status_code=201)
def stock_in_medicines(
    data: StockInRequest,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("pharmacist")),
):
    try:
        return stock_in(db, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/stocks", response_model=list[StockResponse])
def get_stocks(drug_id: int | None = None, db: Session = Depends(get_db)):
    return list_stocks(db, drug_id)


@router.get("/stocks/{stock_id}", response_model=StockResponse)
def get_stock_one(stock_id: int, db: Session = Depends(get_db)):
    stock = get_stock(db, stock_id)
    if not stock:
        raise HTTPException(status_code=404, detail="库存记录不存在")
    return stock
