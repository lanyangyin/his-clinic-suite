from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.modules.auth.security import require_role

from .schemas import (
    MaterialItemCreate,
    MaterialItemResponse,
    MaterialStockResponse,
    StockInCreate,
    UsageCreate,
    UsageResponse,
)
from .service import (
    create_item,
    get_item,
    list_stocks,
    list_usages,
    stock_in,
    use_material,
)

router = APIRouter(prefix="/materials", tags=["materials"])


@router.post("/items/", response_model=MaterialItemResponse, status_code=201)
def new_item(
    data: MaterialItemCreate,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("admin")),
):
    try:
        return create_item(db, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/items/{item_id}", response_model=MaterialItemResponse)
def get_item_one(item_id: int, db: Session = Depends(get_db)):
    item = get_item(db, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="物资不存在")
    return item


@router.post("/stock-in", response_model=MaterialStockResponse, status_code=201)
def stock_in_materials(
    data: StockInCreate,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("admin")),
):
    try:
        return stock_in(db, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/stocks", response_model=list[MaterialStockResponse])
def get_stocks(item_id: int | None = None, db: Session = Depends(get_db)):
    return list_stocks(db, item_id)


@router.post("/usages", response_model=UsageResponse, status_code=201)
def use(
    data: UsageCreate,
    db: Session = Depends(get_db),
    user=Depends(require_role("nurse")),
):
    try:
        return use_material(db, data, user.username)
    except ValueError as e:
        code = 404 if str(e) in {"就诊记录不存在"} else 400
        raise HTTPException(status_code=code, detail=str(e))


@router.get("/usages", response_model=list[UsageResponse])
def get_usages(item_id: int | None = None, db: Session = Depends(get_db)):
    return list_usages(db, item_id)
