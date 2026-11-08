from sqlalchemy.orm import Session

from .models import Supplier
from .schemas import SupplierCreate


def create_supplier(db: Session, data: SupplierCreate) -> Supplier:
    """维护供应商：编码唯一。"""
    existing = db.query(Supplier).filter(Supplier.code == data.code).first()
    if existing:
        raise ValueError("供应商编码已存在")

    supplier = Supplier(**data.model_dump())
    db.add(supplier)
    db.commit()
    db.refresh(supplier)
    return supplier


def get_supplier(db: Session, supplier_id: int) -> Supplier | None:
    return db.get(Supplier, supplier_id)


def list_suppliers(db: Session) -> list[Supplier]:
    return db.query(Supplier).order_by(Supplier.id).all()
