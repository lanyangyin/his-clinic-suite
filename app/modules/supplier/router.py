from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.modules.auth.security import require_role

from .schemas import SupplierCreate, SupplierResponse
from .service import create_supplier, get_supplier, list_suppliers

router = APIRouter(prefix="/suppliers", tags=["suppliers"])


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


@router.get("/", response_model=list[SupplierResponse])
def get_all(db: Session = Depends(get_db)):
    return list_suppliers(db)


@router.get("/{supplier_id}", response_model=SupplierResponse)
def get_one(supplier_id: int, db: Session = Depends(get_db)):
    supplier = get_supplier(db, supplier_id)
    if not supplier:
        raise HTTPException(status_code=404, detail="供应商不存在")
    return supplier
