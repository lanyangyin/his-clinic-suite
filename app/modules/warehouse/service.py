from datetime import datetime

from sqlalchemy.orm import Session

from app.modules.drug.service import get_drug
from app.modules.pharmacy.models import DrugStock
from app.modules.supplier.service import get_supplier

from .models import PurchaseRecord, WarehouseCheck, WarehouseStock
from .schemas import CheckCreate, PurchaseCreate, TransferCreate


def get_warehouse_stock(
    db: Session, drug_id: int, batch_no: str
) -> WarehouseStock | None:
    return (
        db.query(WarehouseStock)
        .filter(
            WarehouseStock.drug_id == drug_id,
            WarehouseStock.batch_no == batch_no,
        )
        .first()
    )


def purchase(
    db: Session, data: PurchaseCreate, purchased_by: str = ""
) -> WarehouseStock:
    """采购入库：同药品同批次合并数量，并记录采购流水（可关联供应商）。"""
    if not get_drug(db, data.drug_id):
        raise ValueError("药品不存在")
    if data.supplier_id is not None and not get_supplier(db, data.supplier_id):
        raise ValueError("供应商不存在")

    stock = get_warehouse_stock(db, data.drug_id, data.batch_no)
    if stock:
        stock.quantity += data.quantity
    else:
        stock = WarehouseStock(
            drug_id=data.drug_id,
            batch_no=data.batch_no,
            expiry=data.expiry,
            quantity=data.quantity,
        )
        db.add(stock)

    db.add(
        PurchaseRecord(
            drug_id=data.drug_id,
            batch_no=data.batch_no,
            quantity=data.quantity,
            supplier_id=data.supplier_id,
            purchased_by=purchased_by,
        )
    )
    db.commit()
    db.refresh(stock)
    return stock


def list_stocks(db: Session, drug_id: int | None = None) -> list[WarehouseStock]:
    """药库库存列表（可按药品过滤）。"""
    query = db.query(WarehouseStock)
    if drug_id is not None:
        query = query.filter(WarehouseStock.drug_id == drug_id)
    return query.order_by(WarehouseStock.id).all()


def transfer(db: Session, data: TransferCreate) -> dict:
    """调拨：药库扣减 → 药房同批次入库（不存在则新建）。"""
    wh = get_warehouse_stock(db, data.drug_id, data.batch_no)
    if not wh:
        raise ValueError("药库无该批次库存")
    if wh.quantity < data.quantity:
        raise ValueError("药库库存不足")

    wh.quantity -= data.quantity

    pharmacy = (
        db.query(DrugStock)
        .filter(
            DrugStock.drug_id == data.drug_id,
            DrugStock.batch_no == data.batch_no,
        )
        .first()
    )
    if pharmacy:
        pharmacy.quantity += data.quantity
    else:
        pharmacy = DrugStock(
            drug_id=data.drug_id,
            batch_no=data.batch_no,
            expiry=wh.expiry,
            location="",
            quantity=data.quantity,
        )
        db.add(pharmacy)

    db.commit()
    db.refresh(wh)
    db.refresh(pharmacy)
    return {
        "drug_id": data.drug_id,
        "batch_no": data.batch_no,
        "transferred_quantity": data.quantity,
        "warehouse_quantity": wh.quantity,
        "pharmacy_stock_id": pharmacy.id,
        "pharmacy_quantity": pharmacy.quantity,
    }


def check(db: Session, data: CheckCreate, checked_by: str = "") -> WarehouseCheck:
    """盘点：按实际数量调整库存，并留痕差异（盘盈/盘亏）。"""
    wh = get_warehouse_stock(db, data.drug_id, data.batch_no)
    if not wh:
        raise ValueError("药库无该批次库存")

    expected = wh.quantity
    diff = data.actual_quantity - expected
    wh.quantity = data.actual_quantity

    record = WarehouseCheck(
        drug_id=data.drug_id,
        batch_no=data.batch_no,
        expected_quantity=expected,
        actual_quantity=data.actual_quantity,
        diff=diff,
        checked_by=checked_by,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def list_checks(db: Session, drug_id: int | None = None) -> list[WarehouseCheck]:
    """盘点记录（可按药品过滤，按时间倒序）。"""
    query = db.query(WarehouseCheck)
    if drug_id is not None:
        query = query.filter(WarehouseCheck.drug_id == drug_id)
    return query.order_by(WarehouseCheck.id.desc()).all()


def list_purchases(
    db: Session, drug_id: int | None = None, supplier_id: int | None = None
) -> list[PurchaseRecord]:
    """采购流水（可按药品/供应商过滤，按时间倒序）。"""
    query = db.query(PurchaseRecord)
    if drug_id is not None:
        query = query.filter(PurchaseRecord.drug_id == drug_id)
    if supplier_id is not None:
        query = query.filter(PurchaseRecord.supplier_id == supplier_id)
    return query.order_by(PurchaseRecord.id.desc()).all()
