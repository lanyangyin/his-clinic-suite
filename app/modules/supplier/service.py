from datetime import date, timedelta

from sqlalchemy.orm import Session

from .models import Supplier
from .schemas import SupplierCreate, SupplierUpdate


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


def update_supplier(db: Session, supplier_id: int, data: SupplierUpdate) -> Supplier:
    supplier = db.get(Supplier, supplier_id)
    if not supplier:
        raise ValueError("供应商不存在")
    for key, value in data.model_dump(exclude_none=True).items():
        setattr(supplier, key, value)
    db.commit()
    db.refresh(supplier)
    return supplier


def get_supplier(db: Session, supplier_id: int) -> Supplier | None:
    return db.get(Supplier, supplier_id)


def list_suppliers(db: Session) -> list[Supplier]:
    return db.query(Supplier).order_by(Supplier.id).all()


def suspend_expired(db: Session) -> int:
    """将证照已过期且仍为 active 的供应商批量停用。"""
    rows = (
        db.query(Supplier)
        .filter(
            Supplier.status == "active",
            Supplier.license_expiry.is_not(None),
            Supplier.license_expiry < date.today(),
        )
        .all()
    )
    for row in rows:
        row.status = "suspended"
        row.blacklist_reason = "证照过期自动停用"
    db.commit()
    return len(rows)


def list_expiring_suppliers(db: Session, days: int = 90) -> list[Supplier]:
    deadline = date.today() + timedelta(days=max(days, 0))
    return (
        db.query(Supplier)
        .filter(
            Supplier.license_expiry.is_not(None),
            Supplier.license_expiry <= deadline,
        )
        .order_by(Supplier.license_expiry)
        .all()
    )
