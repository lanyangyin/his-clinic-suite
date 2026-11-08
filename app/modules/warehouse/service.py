from datetime import datetime

from sqlalchemy.orm import Session

from app.modules.drug.service import get_drug
from app.modules.materials.models import MaterialStock
from app.modules.materials.service import get_item as get_material_item
from app.modules.pharmacy.models import DrugStock
from app.modules.stock_ledger.service import record_drug, record_material
from app.modules.supplier.service import get_supplier

from .models import (
    OutboundItem,
    OutboundOrder,
    PurchaseRecord,
    WarehouseCheck,
    WarehouseStock,
)
from .schemas import CheckCreate, OutboundOrderCreate, PurchaseCreate, TransferCreate


def receive_stock(
    db: Session, drug_id: int, batch_no: str, expiry, quantity: int
) -> WarehouseStock:
    """总库收货（不提交事务）：同药同批合并数量。"""
    existing = get_warehouse_stock(db, drug_id, batch_no)
    if existing:
        existing.quantity += quantity
        return existing
    stock = WarehouseStock(
        drug_id=drug_id, batch_no=batch_no, expiry=expiry, quantity=quantity
    )
    db.add(stock)
    db.flush()
    return stock


def create_outbound(
    db: Session, data: OutboundOrderCreate, applicant: str = ""
) -> OutboundOrder:
    """药房/科室申请出库：校验药品/物资，生成出库单（待审核）。"""
    items = []
    for item in data.items:
        if item.kind == "drug":
            if not item.drug_id:
                raise ValueError("药品行缺少 drug_id")
            drug = get_drug(db, item.drug_id)
            if not drug:
                raise ValueError(f"药品不存在：{item.drug_id}")
            if not item.batch_no:
                raise ValueError(f"药品「{drug.name}」必须指定批号")
            price = item.unit_price or drug.base_price
            items.append(
                OutboundItem(
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
                    insurance_code=drug.insurance_code,
                )
            )
        else:
            if not item.material_id:
                raise ValueError("物资行缺少 material_id")
            material = get_material_item(db, item.material_id)
            if not material:
                raise ValueError(f"物资不存在：{item.material_id}")
            price = item.unit_price or material.price
            items.append(
                OutboundItem(
                    kind="material",
                    material_id=material.id,
                    name=material.name,
                    spec=material.spec,
                    unit=material.unit,
                    quantity=item.quantity,
                    unit_price=price,
                    amount=round(item.quantity * price, 2),
                )
            )
    if not items:
        raise ValueError("出库单至少需要一行明细")

    last = db.query(OutboundOrder.id).order_by(OutboundOrder.id.desc()).first()
    next_id = (last[0] if last else 0) + 1
    order = OutboundOrder(
        outbound_no=f"OUT{datetime.now():%Y%m%d}{next_id:04d}",
        outbound_type=data.outbound_type,
        target_type=data.target_type,
        target_name=data.target_name,
        note=data.note,
        applicant=applicant,
        status="submitted",
        items=items,
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return order


def get_outbound(db: Session, order_id: int) -> OutboundOrder | None:
    return db.get(OutboundOrder, order_id)


def list_outbounds(
    db: Session, status: str | None = None, target_type: str | None = None
) -> list[OutboundOrder]:
    query = db.query(OutboundOrder)
    if status:
        query = query.filter(OutboundOrder.status == status)
    if target_type:
        query = query.filter(OutboundOrder.target_type == target_type)
    return query.order_by(OutboundOrder.id.desc()).all()


def approve_outbound(db: Session, order_id: int, approver: str) -> OutboundOrder:
    order = get_outbound(db, order_id)
    if not order:
        raise ValueError("出库单不存在")
    if order.status != "submitted":
        raise ValueError("仅已申请状态的出库单可以审核")
    order.status = "approved"
    order.approver = approver
    order.approved_at = datetime.now()
    db.commit()
    db.refresh(order)
    return order


def issue_outbound(db: Session, order_id: int, issuer: str) -> OutboundOrder:
    """库房出库：扣总库库存，增药房批次库存 / 科室物资库存。"""
    order = get_outbound(db, order_id)
    if not order:
        raise ValueError("出库单不存在")
    if order.status != "approved":
        raise ValueError("仅已审核的出库单可以出库")

    for item in order.items:
        if item.kind == "drug":
            warehouse_stock = (
                db.query(WarehouseStock)
                .filter(
                    WarehouseStock.drug_id == item.drug_id,
                    WarehouseStock.batch_no == item.batch_no,
                )
                .first()
            )
            if not warehouse_stock or warehouse_stock.quantity < item.quantity:
                db.rollback()
                raise ValueError(f"总库库存不足：{item.name}（批次 {item.batch_no}）")
            expiry = item.expiry or warehouse_stock.expiry

            affected = (
                db.query(WarehouseStock)
                .filter(
                    WarehouseStock.id == warehouse_stock.id,
                    WarehouseStock.quantity >= item.quantity,
                )
                .update(
                    {WarehouseStock.quantity: WarehouseStock.quantity - item.quantity},
                    synchronize_session=False,
                )
            )
            if affected != 1:
                db.rollback()
                raise ValueError(f"总库库存不足：{item.name}（批次 {item.batch_no}）")

            drug = get_drug(db, item.drug_id)
            db.expire(warehouse_stock)
            record_drug(
                db,
                drug,
                batch_no=item.batch_no,
                expiry=expiry,
                warehouse="总库",
                direction="out",
                quantity=item.quantity,
                unit_price=item.unit_price,
                ref_type="outbound",
                ref_id=order.id,
                operator=issuer,
                note=f"出库单 {order.outbound_no}",
            )

            stock = (
                db.query(DrugStock)
                .filter(
                    DrugStock.drug_id == item.drug_id,
                    DrugStock.batch_no == item.batch_no,
                )
                .first()
            )
            if stock:
                stock.quantity += item.quantity
            else:
                db.add(
                    DrugStock(
                        drug_id=item.drug_id,
                        batch_no=item.batch_no,
                        expiry=expiry,
                        quantity=item.quantity,
                    )
                )
            db.flush()
            record_drug(
                db,
                drug,
                batch_no=item.batch_no,
                expiry=expiry,
                warehouse="药房",
                direction="in",
                quantity=item.quantity,
                unit_price=item.unit_price,
                ref_type="outbound",
                ref_id=order.id,
                operator=issuer,
                note=f"出库单 {order.outbound_no}",
            )
        else:
            affected = (
                db.query(MaterialStock)
                .filter(
                    MaterialStock.item_id == item.material_id,
                    MaterialStock.warehouse == "总库",
                    MaterialStock.quantity >= item.quantity,
                )
                .update(
                    {MaterialStock.quantity: MaterialStock.quantity - item.quantity},
                    synchronize_session=False,
                )
            )
            if affected != 1:
                db.rollback()
                raise ValueError(f"总库库存不足：{item.name}")

            material = get_material_item(db, item.material_id)
            record_material(
                db,
                material,
                warehouse="总库",
                direction="out",
                quantity=item.quantity,
                unit_price=item.unit_price,
                ref_type="outbound",
                ref_id=order.id,
                operator=issuer,
                note=f"出库单 {order.outbound_no}",
            )

            target = order.target_name or "药房"
            stock = (
                db.query(MaterialStock)
                .filter(
                    MaterialStock.item_id == item.material_id,
                    MaterialStock.warehouse == target,
                )
                .first()
            )
            if stock:
                stock.quantity += item.quantity
            else:
                db.add(
                    MaterialStock(
                        item_id=item.material_id,
                        warehouse=target,
                        quantity=item.quantity,
                    )
                )
            db.flush()
            record_material(
                db,
                material,
                warehouse=target,
                direction="in",
                quantity=item.quantity,
                unit_price=item.unit_price,
                ref_type="outbound",
                ref_id=order.id,
                operator=issuer,
                note=f"出库单 {order.outbound_no}",
            )

    order.status = "issued"
    order.issuer = issuer
    order.issued_at = datetime.now()
    db.commit()
    db.refresh(order)
    return order


def cancel_outbound(db: Session, order_id: int) -> OutboundOrder:
    order = get_outbound(db, order_id)
    if not order:
        raise ValueError("出库单不存在")
    if order.status == "issued":
        raise ValueError("已出库的出库单不能取消")
    if order.status == "cancelled":
        raise ValueError("该出库单已取消")
    order.status = "cancelled"
    db.commit()
    db.refresh(order)
    return order


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
    drug = get_drug(db, data.drug_id)
    if not drug:
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

    purchase_record = PurchaseRecord(
        drug_id=data.drug_id,
        batch_no=data.batch_no,
        quantity=data.quantity,
        supplier_id=data.supplier_id,
        purchased_by=purchased_by,
    )
    db.add(purchase_record)
    db.flush()
    record_drug(
        db,
        drug,
        batch_no=data.batch_no,
        expiry=data.expiry,
        warehouse="总库",
        direction="in",
        quantity=data.quantity,
        unit_price=drug.base_price,
        ref_type="purchase",
        ref_id=purchase_record.id,
        operator=purchased_by,
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


def transfer(db: Session, data: TransferCreate, operator: str = "") -> dict:
    """调拨：药库扣减 → 药房同批次入库（不存在则新建），并记双向流水。"""
    drug = get_drug(db, data.drug_id)
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

    db.flush()
    for warehouse_name, direction in (("总库", "out"), ("药房", "in")):
        record_drug(
            db,
            drug,
            batch_no=data.batch_no,
            expiry=wh.expiry,
            warehouse=warehouse_name,
            direction=direction,
            quantity=data.quantity,
            unit_price=drug.base_price,
            ref_type="transfer",
            operator=operator,
        )
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
    """盘点：按实际数量调整库存，留痕差异并记调整流水。"""
    drug = get_drug(db, data.drug_id)
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
    db.flush()
    if diff != 0:
        record_drug(
            db,
            drug,
            batch_no=data.batch_no,
            expiry=wh.expiry,
            warehouse="总库",
            direction="in" if diff > 0 else "out",
            quantity=abs(diff),
            unit_price=drug.base_price,
            ref_type="adjust",
            ref_id=record.id,
            operator=checked_by,
            note=f"盘点差异 {diff:+d}",
        )
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
