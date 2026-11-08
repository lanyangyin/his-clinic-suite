"""入库单：收货 → 验收 → 入库（药品/器械/耗材/办公用品统一入口）。

医疗规范要点：
- 药品必须登记批号、有效期与储存条件（常温/阴凉/冷藏），按批入库；
- 医疗器械（device）必须登记注册证号；
- 验收可登记不合格数量与原因，入库只入合格数量；
- 供应商、随货同行单号、发票号留痕，供医保进销存上传与追溯。
"""
from datetime import datetime

from sqlalchemy.orm import Session

from app.modules.drug.service import get_drug
from app.modules.materials.service import get_item as get_material_item
from app.modules.materials.schemas import StockInCreate
from app.modules.materials.service import stock_in as material_stock_in
from app.modules.supplier.service import get_supplier
from app.modules.warehouse.service import receive_stock as warehouse_receive

from .models import InboundItem, InboundOrder
from .schemas import InboundCheckRequest, InboundOrderCreate


def _build_items(db: Session, data: InboundOrderCreate) -> list[InboundItem]:
    items = []
    for item in data.items:
        if item.kind == "drug":
            if not item.drug_id:
                raise ValueError("药品行缺少 drug_id")
            drug = get_drug(db, item.drug_id)
            if not drug:
                raise ValueError(f"药品不存在：{item.drug_id}")
            if not item.batch_no:
                raise ValueError(f"药品「{drug.name}」必须填写批号")
            if not item.expiry:
                raise ValueError(f"药品「{drug.name}」必须填写有效期")
            price = item.unit_price or drug.base_price
            items.append(
                InboundItem(
                    kind="drug",
                    drug_id=drug.id,
                    name=drug.name,
                    spec=drug.spec,
                    unit=drug.unit,
                    batch_no=item.batch_no,
                    expiry=item.expiry,
                    quantity=item.quantity,
                    unit_price=price,
                    amount=round(item.quantity * price, 2),
                    insurance_code=item.insurance_code or drug.insurance_code,
                    manufacturer=item.manufacturer or drug.manufacturer,
                    storage_condition=item.storage_condition,
                    warehouse=item.warehouse,
                    location=item.location,
                    note=item.note,
                )
            )
        else:
            if not item.material_id:
                raise ValueError("物资行缺少 material_id")
            material = get_material_item(db, item.material_id)
            if not material:
                raise ValueError(f"物资不存在：{item.material_id}")
            registration_no = item.registration_no or material.registration_no
            if material.category == "device" and not registration_no:
                raise ValueError(f"医疗器械「{material.name}」必须填写注册证号")
            price = item.unit_price or material.price
            items.append(
                InboundItem(
                    kind="material",
                    material_id=material.id,
                    name=material.name,
                    spec=material.spec,
                    unit=material.unit,
                    batch_no=item.batch_no,
                    expiry=item.expiry,
                    quantity=item.quantity,
                    unit_price=price,
                    amount=round(item.quantity * price, 2),
                    registration_no=registration_no,
                    manufacturer=item.manufacturer or material.manufacturer,
                    warehouse=item.warehouse,
                    location=item.location,
                    note=item.note,
                )
            )
    if not items:
        raise ValueError("入库单至少需要一行明细")
    return items


def create_order(
    db: Session, data: InboundOrderCreate, received_by: str = ""
) -> InboundOrder:
    if data.supplier_id and not get_supplier(db, data.supplier_id):
        raise ValueError("供应商不存在")

    items = _build_items(db, data)
    next_id = (db.query(InboundOrder.id).order_by(InboundOrder.id.desc()).first() or (0,))[0] + 1
    order = InboundOrder(
        order_no=f"IN{datetime.now():%Y%m%d}{next_id:04d}",
        order_type=data.order_type,
        supplier_id=data.supplier_id,
        source=data.source,
        delivery_no=data.delivery_no,
        invoice_no=data.invoice_no,
        note=data.note,
        received_by=received_by,
        received_at=datetime.now(),
        status="received",
        items=items,
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return order


def get_order(db: Session, order_id: int) -> InboundOrder | None:
    return db.get(InboundOrder, order_id)


def list_orders(
    db: Session, status: str | None = None, order_type: str | None = None
) -> list[InboundOrder]:
    query = db.query(InboundOrder)
    if status:
        query = query.filter(InboundOrder.status == status)
    if order_type:
        query = query.filter(InboundOrder.order_type == order_type)
    return query.order_by(InboundOrder.id.desc()).all()


def check_order(
    db: Session, order_id: int, data: InboundCheckRequest, checked_by: str
) -> InboundOrder:
    """验收：登记不合格数量/原因，状态置 checked。"""
    order = get_order(db, order_id)
    if not order:
        raise ValueError("入库单不存在")
    if order.status != "received":
        raise ValueError("仅已收货的入库单可以验收")

    checked_at = datetime.now()
    rejected = {item.item_id: item for item in data.items}
    order_items = {item.id: item for item in order.items}
    for item_id, check in rejected.items():
        item = order_items.get(item_id)
        if not item:
            raise ValueError(f"明细不存在：{item_id}")
        if check.rejected_qty > item.quantity:
            raise ValueError(f"不合格数量不能大于到货数量：{item.name}")
        item.rejected_qty = check.rejected_qty
        item.reject_reason = check.reject_reason

    order.status = "checked"
    order.checked_by = checked_by
    order.checked_at = checked_at
    db.commit()
    db.refresh(order)
    return order


def stock_order(db: Session, order_id: int) -> InboundOrder:
    """入库：合格数量写入药房批次库存 / 物资库存，状态置 stocked。"""
    order = get_order(db, order_id)
    if not order:
        raise ValueError("入库单不存在")
    if order.status != "checked":
        raise ValueError("仅已验收的入库单可以入库")

    for item in order.items:
        quantity = item.quantity - item.rejected_qty
        if quantity <= 0:
            continue
        if item.kind == "drug":
            # 入库进总库（药库），药房通过出库单领用
            warehouse_receive(db, item.drug_id, item.batch_no, item.expiry, quantity)
        else:
            material_stock_in(
                db,
                StockInCreate(
                    item_id=item.material_id,
                    warehouse=item.warehouse,
                    quantity=quantity,
                ),
            )

    order.status = "stocked"
    order.stocked_at = datetime.now()
    db.commit()
    db.refresh(order)
    return order


def cancel_order(db: Session, order_id: int) -> InboundOrder:
    order = get_order(db, order_id)
    if not order:
        raise ValueError("入库单不存在")
    if order.status == "stocked":
        raise ValueError("已入库的入库单不能取消")
    if order.status == "cancelled":
        raise ValueError("该入库单已取消")
    order.status = "cancelled"
    db.commit()
    db.refresh(order)
    return order
