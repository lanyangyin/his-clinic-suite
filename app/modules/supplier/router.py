from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.modules.auth.security import require_read_login, require_role

from .schemas import SupplierCreate, SupplierResponse, SupplierUpdate
from .service import (
    create_supplier,
    get_supplier,
    list_expiring_suppliers,
    list_suppliers,
    update_supplier,
)

router = APIRouter(prefix="/suppliers", tags=["suppliers"], dependencies=[Depends(require_read_login)])


@router.post("/", response_model=SupplierResponse, status_code=201)
def new_supplier(
    data: SupplierCreate,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("admin")),
):
    try:
        return create_supplier(db, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{supplier_id}", response_model=SupplierResponse)
def edit_supplier(
    supplier_id: int,
    data: SupplierUpdate,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("admin")),
):
    try:
        return update_supplier(db, supplier_id, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/expiring", response_model=list[SupplierResponse])
def get_expiring(days: int = 90, db: Session = Depends(get_db)):
    """证照在 N 天内到期或已过期的供应商。"""
    return list_expiring_suppliers(db, days)


@router.get("/", response_model=list[SupplierResponse])
def get_all(db: Session = Depends(get_db)):
    return list_suppliers(db)


@router.get("/{supplier_id}", response_model=SupplierResponse)
def get_one(supplier_id: int, db: Session = Depends(get_db)):
    supplier = get_supplier(db, supplier_id)
    if not supplier:
        raise HTTPException(status_code=404, detail="供应商不存在")
    return supplier
