"""手术/治疗室耗材扣减与材料费。"""
from sqlalchemy.orm import Session

from app.modules.charges.service import add_charge
from app.modules.materials.models import MaterialStock
from app.modules.materials.service import get_item as get_material
from app.modules.stock_ledger.service import record_material

from .models import ProcedureMaterial


def consume_material(
    db: Session,
    *,
    source_type: str,
    source_id: int,
    encounter_id: int | None,
    material_id: int,
    quantity: int,
    warehouse: str,
    operator: str = "",
    commit: bool = True,
) -> ProcedureMaterial:
    material = get_material(db, material_id)
    if not material:
        raise ValueError("物资不存在")
    stock = (
        db.query(MaterialStock)
        .filter(
            MaterialStock.item_id == material_id,
            MaterialStock.warehouse == warehouse,
        )
        .first()
    )
    if not stock or stock.quantity < quantity:
        raise ValueError(f"{warehouse} 库存不足：{material.name}")
    stock.quantity -= quantity
    row = ProcedureMaterial(
        source_type=source_type,
        source_id=source_id,
        encounter_id=encounter_id,
        material_id=material_id,
        name=material.name,
        quantity=quantity,
        unit_price=material.price,
        amount=round(material.price * quantity, 2),
        warehouse=warehouse,
        operator=operator,
    )
    db.add(row)
    db.flush()
    record_material(
        db,
        material,
        warehouse=warehouse,
        direction="out",
        quantity=quantity,
        unit_price=material.price,
        ref_type=f"{source_type}_material",
        ref_id=row.id,
        operator=operator,
    )
    if encounter_id is not None and material.price > 0:
        add_charge(
            db,
            encounter_id=encounter_id,
            source_type="procedure_material",
            source_id=row.id,
            charge_type="material",
            item_name=f"材料：{material.name}",
            quantity=quantity,
            unit_price=material.price,
            insurance_ratio=0.0,
        )
    if commit:
        db.commit()
        db.refresh(row)
    else:
        db.flush()
    return row
