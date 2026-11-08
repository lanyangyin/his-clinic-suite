"""库存流水台账：记录每笔入/出并计算结存（不提交事务）。"""
from datetime import date, datetime

from sqlalchemy.orm import Session

from app.modules.materials.models import MaterialStock
from app.modules.pharmacy.models import DrugStock
from app.modules.warehouse.models import WarehouseStock

from .models import StockMovement


def _drug_balance(db: Session, drug_id: int, batch_no: str, warehouse: str) -> int:
    if warehouse == "总库":
        row = (
            db.query(WarehouseStock)
            .filter(
                WarehouseStock.drug_id == drug_id,
                WarehouseStock.batch_no == batch_no,
            )
            .first()
        )
    else:
        row = (
            db.query(DrugStock)
            .filter(DrugStock.drug_id == drug_id, DrugStock.batch_no == batch_no)
            .first()
        )
    return row.quantity if row else 0


def _material_balance(db: Session, item_id: int, warehouse: str) -> int:
    row = (
        db.query(MaterialStock)
        .filter(
            MaterialStock.item_id == item_id,
            MaterialStock.warehouse == warehouse,
        )
        .first()
    )
    return row.quantity if row else 0


def record_drug(
    db: Session,
    drug,
    *,
    batch_no: str,
    expiry: date | None,
    warehouse: str,
    direction: str,
    quantity: int,
    unit_price: float = 0.0,
    ref_type: str = "",
    ref_id: int | None = None,
    operator: str = "",
    note: str = "",
) -> StockMovement:
    movement = StockMovement(
        kind="drug",
        drug_id=drug.id,
        name=drug.name,
        spec=drug.spec,
        unit=drug.unit,
        batch_no=batch_no,
        expiry=expiry,
        warehouse=warehouse,
        direction=direction,
        quantity=quantity,
        unit_price=unit_price,
        amount=round(quantity * unit_price, 2),
        balance_after=_drug_balance(db, drug.id, batch_no, warehouse),
        ref_type=ref_type,
        ref_id=ref_id,
        operator=operator,
        note=note,
    )
    db.add(movement)
    return movement


def record_material(
    db: Session,
    material,
    *,
    warehouse: str,
    direction: str,
    quantity: int,
    unit_price: float = 0.0,
    batch_no: str = "",
    ref_type: str = "",
    ref_id: int | None = None,
    operator: str = "",
    note: str = "",
) -> StockMovement:
    movement = StockMovement(
        kind="material",
        material_id=material.id,
        name=material.name,
        spec=material.spec,
        unit=material.unit,
        batch_no=batch_no,
        warehouse=warehouse,
        direction=direction,
        quantity=quantity,
        unit_price=unit_price,
        amount=round(quantity * unit_price, 2),
        balance_after=_material_balance(db, material.id, warehouse),
        ref_type=ref_type,
        ref_id=ref_id,
        operator=operator,
        note=note,
    )
    db.add(movement)
    return movement


def list_movements(
    db: Session,
    kind: str | None = None,
    drug_id: int | None = None,
    material_id: int | None = None,
    warehouse: str | None = None,
    direction: str | None = None,
    ref_type: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    limit: int = 200,
    offset: int = 0,
) -> list[StockMovement]:
    query = db.query(StockMovement)
    if kind:
        query = query.filter(StockMovement.kind == kind)
    if drug_id is not None:
        query = query.filter(StockMovement.drug_id == drug_id)
    if material_id is not None:
        query = query.filter(StockMovement.material_id == material_id)
    if warehouse:
        query = query.filter(StockMovement.warehouse == warehouse)
    if direction:
        query = query.filter(StockMovement.direction == direction)
    if ref_type:
        query = query.filter(StockMovement.ref_type == ref_type)
    if start_date:
        query = query.filter(
            StockMovement.created_at >= datetime.combine(start_date, datetime.min.time())
        )
    if end_date:
        query = query.filter(
            StockMovement.created_at <= datetime.combine(end_date, datetime.max.time())
        )
    return (
        query.order_by(StockMovement.id.desc())
        .offset(max(offset, 0))
        .limit(min(max(limit, 1), 500))
        .all()
    )
