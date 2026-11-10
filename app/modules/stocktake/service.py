"""药品/耗材盘点。"""
from datetime import datetime

from sqlalchemy.orm import Session

from app.modules.drug.models import Drug
from app.modules.materials.models import MaterialItem, MaterialStock
from app.modules.stock_ledger.service import record_drug, record_material
from app.modules.warehouse.models import WarehouseStock

from .models import Stocktake, StocktakeItem
from .schemas import StocktakeCounts, StocktakeCreate


def _next_no(db: Session) -> str:
    last = db.query(Stocktake.id).order_by(Stocktake.id.desc()).first()
    return f"ST{datetime.now():%Y%m%d}{(last[0] if last else 0) + 1:04d}"


def create_stocktake(db: Session, data: StocktakeCreate, operator: str = "") -> Stocktake:
    take = Stocktake(
        take_no=_next_no(db),
        title=data.title or ("药品盘点" if data.kind == "drug" else "耗材盘点"),
        kind=data.kind,
        warehouse=data.warehouse,
        note=data.note,
        created_by=operator,
    )
    db.add(take)
    db.flush()
    if data.kind == "drug":
        rows = (
            db.query(WarehouseStock, Drug)
            .join(Drug, WarehouseStock.drug_id == Drug.id)
            .filter(WarehouseStock.quantity > 0)
            .order_by(Drug.name, WarehouseStock.batch_no)
            .all()
        )
        for stock, drug in rows:
            db.add(
                StocktakeItem(
                    take_id=take.id,
                    kind="drug",
                    drug_id=drug.id,
                    name=drug.name,
                    spec=drug.spec,
                    batch_no=stock.batch_no,
                    warehouse="药库",
                    book_quantity=stock.quantity,
                    unit_price=drug.base_price,
                )
            )
    else:
        rows = (
            db.query(MaterialStock, MaterialItem)
            .join(MaterialItem, MaterialStock.item_id == MaterialItem.id)
            .filter(
                MaterialStock.warehouse == data.warehouse,
                MaterialStock.quantity > 0,
            )
            .order_by(MaterialItem.name)
            .all()
        )
        for stock, item in rows:
            db.add(
                StocktakeItem(
                    take_id=take.id,
                    kind="material",
                    material_id=item.id,
                    name=item.name,
                    spec=item.spec,
                    warehouse=stock.warehouse,
                    book_quantity=stock.quantity,
                    unit_price=item.price,
                )
            )
    db.commit()
    db.refresh(take)
    return take


def list_stocktakes(db: Session, status: str | None = None) -> list[Stocktake]:
    query = db.query(Stocktake)
    if status:
        query = query.filter(Stocktake.status == status)
    return query.order_by(Stocktake.id.desc()).all()


def get_stocktake(db: Session, take_id: int) -> Stocktake | None:
    return db.get(Stocktake, take_id)


def save_counts(db: Session, take_id: int, data: StocktakeCounts) -> Stocktake:
    take = get_stocktake(db, take_id)
    if not take:
        raise ValueError("盘点单不存在")
    if take.status != "counting":
        raise ValueError("该盘点单已结束")
    items = {row.id: row for row in take.items}
    for update in data.items:
        row = items.get(update.item_id)
        if not row:
            raise ValueError(f"盘点明细不存在：{update.item_id}")
        row.actual_quantity = update.actual_quantity
    db.commit()
    db.refresh(take)
    return take


def complete_stocktake(db: Session, take_id: int, operator: str = "") -> Stocktake:
    take = get_stocktake(db, take_id)
    if not take:
        raise ValueError("盘点单不存在")
    if take.status != "counting":
        raise ValueError("该盘点单已结束")
    uncounted = [row.name for row in take.items if row.actual_quantity is None]
    if uncounted:
        raise ValueError(f"还有 {len(uncounted)} 项未录入实盘数")
    for row in take.items:
        diff = (row.actual_quantity or 0) - row.book_quantity
        if diff == 0:
            continue
        if row.kind == "drug":
            stock = (
                db.query(WarehouseStock)
                .filter(
                    WarehouseStock.drug_id == row.drug_id,
                    WarehouseStock.batch_no == row.batch_no,
                )
                .first()
            )
            if stock:
                stock.quantity = row.actual_quantity or 0
            drug = db.get(Drug, row.drug_id)
            if drug:
                record_drug(
                    db,
                    drug,
                    warehouse="药库",
                    direction="in" if diff > 0 else "out",
                    quantity=abs(diff),
                    batch_no=row.batch_no,
                    expiry=stock.expiry if stock else None,
                    unit_price=row.unit_price,
                    ref_type="stocktake",
                    ref_id=take.id,
                    operator=operator,
                    note=f"盘点 {take.take_no} 差异 {diff:+d}",
                )
        else:
            stock = (
                db.query(MaterialStock)
                .filter(
                    MaterialStock.item_id == row.material_id,
                    MaterialStock.warehouse == row.warehouse,
                )
                .first()
            )
            if stock is None:
                stock = MaterialStock(
                    item_id=row.material_id, warehouse=row.warehouse, quantity=0
                )
                db.add(stock)
            stock.quantity = row.actual_quantity or 0
            item = db.get(MaterialItem, row.material_id)
            if item:
                record_material(
                    db,
                    item,
                    warehouse=row.warehouse,
                    direction="in" if diff > 0 else "out",
                    quantity=abs(diff),
                    unit_price=row.unit_price,
                    ref_type="stocktake",
                    ref_id=take.id,
                    operator=operator,
                    note=f"盘点 {take.take_no} 差异 {diff:+d}",
                )
    take.status = "completed"
    take.completed_by = operator
    take.completed_at = datetime.now()
    db.commit()
    db.refresh(take)
    return take


def cancel_stocktake(db: Session, take_id: int) -> Stocktake:
    take = get_stocktake(db, take_id)
    if not take:
        raise ValueError("盘点单不存在")
    if take.status != "counting":
        raise ValueError("该盘点单已结束")
    take.status = "cancelled"
    db.commit()
    db.refresh(take)
    return take
