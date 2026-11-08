from sqlalchemy.orm import Session

from app.modules.encounter.service import get_encounter

from .models import MaterialItem, MaterialStock, MaterialUsage
from .schemas import MaterialItemCreate, StockInCreate, UsageCreate


def create_item(db: Session, data: MaterialItemCreate) -> MaterialItem:
    """维护物资主数据：编码唯一。"""
    existing = db.query(MaterialItem).filter(MaterialItem.code == data.code).first()
    if existing:
        raise ValueError("物资编码已存在")

    item = MaterialItem(**data.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def get_item(db: Session, item_id: int) -> MaterialItem | None:
    return db.get(MaterialItem, item_id)


def list_items(db: Session, category: str | None = None) -> list[MaterialItem]:
    """物资目录（可按分类：器械/耗材/办公）。"""
    query = db.query(MaterialItem)
    if category:
        query = query.filter(MaterialItem.category == category)
    return query.order_by(MaterialItem.id).all()


def stock_in(db: Session, data: StockInCreate) -> MaterialStock:
    """物资入库：同物品同库房合并数量。"""
    if not get_item(db, data.item_id):
        raise ValueError("物资不存在")

    stock = (
        db.query(MaterialStock)
        .filter(
            MaterialStock.item_id == data.item_id,
            MaterialStock.warehouse == data.warehouse,
        )
        .first()
    )
    if stock:
        stock.quantity += data.quantity
        db.commit()
        db.refresh(stock)
        return stock

    stock = MaterialStock(
        item_id=data.item_id, warehouse=data.warehouse, quantity=data.quantity
    )
    db.add(stock)
    db.commit()
    db.refresh(stock)
    return stock


def list_stocks(db: Session, item_id: int | None = None) -> list[MaterialStock]:
    query = db.query(MaterialStock)
    if item_id is not None:
        query = query.filter(MaterialStock.item_id == item_id)
    return query.order_by(MaterialStock.id).all()


def use_material(db: Session, data: UsageCreate, used_by: str = "") -> MaterialUsage:
    """高值耗材使用追溯：校验序列号唯一、库房库存充足，扣减并记录去向。"""
    item = get_item(db, data.item_id)
    if not item:
        raise ValueError("物资不存在")
    if not item.is_high_value:
        raise ValueError("该物资不是高值耗材，无需追溯")
    if db.query(MaterialUsage).filter(MaterialUsage.serial_no == data.serial_no).first():
        raise ValueError("该序列号已使用")
    if not get_encounter(db, data.encounter_id):
        raise ValueError("就诊记录不存在")

    stock = (
        db.query(MaterialStock)
        .filter(
            MaterialStock.item_id == data.item_id,
            MaterialStock.warehouse == data.warehouse,
        )
        .first()
    )
    if not stock or stock.quantity < 1:
        raise ValueError("该库房物资库存不足")

    stock.quantity -= 1
    usage = MaterialUsage(
        item_id=data.item_id,
        serial_no=data.serial_no,
        encounter_id=data.encounter_id,
        warehouse=data.warehouse,
        used_by=used_by,
    )
    db.add(usage)
    db.commit()
    db.refresh(usage)
    return usage


def list_usages(db: Session, item_id: int | None = None) -> list[MaterialUsage]:
    query = db.query(MaterialUsage)
    if item_id is not None:
        query = query.filter(MaterialUsage.item_id == item_id)
    return query.order_by(MaterialUsage.id.desc()).all()
