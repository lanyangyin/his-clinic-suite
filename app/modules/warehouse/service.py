from datetime import date, datetime, timedelta

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
    PurchaseRequest,
    PurchaseRequestItem,
    StockAdjustment,
    WarehouseCheck,
    WarehouseStock,
)
from .schemas import (
    CheckCreate,
    OutboundOrderCreate,
    PurchaseCreate,
    PurchaseOrderRequest,
    PurchaseReceiveRequest,
    PurchaseRejectRequest,
    PurchaseRequestCreate,
    TransferCreate,
)


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
            if not item.batch_no and data.outbound_type != "requisition":
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


def _deduct_drug(
    db: Session, drug_id: int, batch_no: str, quantity: int, warehouse: str, item_name: str
):
    if warehouse == "总库":
        affected = (
            db.query(WarehouseStock)
            .filter(
                WarehouseStock.drug_id == drug_id,
                WarehouseStock.batch_no == batch_no,
                WarehouseStock.quantity >= quantity,
            )
            .update(
                {WarehouseStock.quantity: WarehouseStock.quantity - quantity},
                synchronize_session=False,
            )
        )
        if affected != 1:
            raise ValueError(f"总库库存不足：{item_name}（批次 {batch_no}）")
        row = (
            db.query(WarehouseStock)
            .filter(
                WarehouseStock.drug_id == drug_id,
                WarehouseStock.batch_no == batch_no,
            )
            .first()
        )
        return row.expiry
    affected = (
        db.query(DrugStock)
        .filter(
            DrugStock.drug_id == drug_id,
            DrugStock.batch_no == batch_no,
            DrugStock.quantity >= quantity,
        )
        .update(
            {DrugStock.quantity: DrugStock.quantity - quantity},
            synchronize_session=False,
        )
    )
    if affected != 1:
        raise ValueError(f"{warehouse}库存不足：{item_name}（批次 {batch_no}）")
    row = (
        db.query(DrugStock)
        .filter(DrugStock.drug_id == drug_id, DrugStock.batch_no == batch_no)
        .first()
    )
    return row.expiry


def _add_drug(
    db: Session, drug_id: int, batch_no: str, expiry, quantity: int, warehouse: str
) -> None:
    if warehouse == "总库":
        row = (
            db.query(WarehouseStock)
            .filter(
                WarehouseStock.drug_id == drug_id,
                WarehouseStock.batch_no == batch_no,
            )
            .first()
        )
        if row:
            row.quantity += quantity
        else:
            db.add(
                WarehouseStock(
                    drug_id=drug_id,
                    batch_no=batch_no,
                    expiry=expiry,
                    quantity=quantity,
                )
            )
    else:
        row = (
            db.query(DrugStock)
            .filter(DrugStock.drug_id == drug_id, DrugStock.batch_no == batch_no)
            .first()
        )
        if row:
            row.quantity += quantity
        else:
            db.add(
                DrugStock(
                    drug_id=drug_id,
                    batch_no=batch_no,
                    expiry=expiry,
                    location="",
                    quantity=quantity,
                )
            )


def _deduct_material(
    db: Session, item_id: int, quantity: int, warehouse: str, item_name: str
) -> None:
    affected = (
        db.query(MaterialStock)
        .filter(
            MaterialStock.item_id == item_id,
            MaterialStock.warehouse == warehouse,
            MaterialStock.quantity >= quantity,
        )
        .update(
            {MaterialStock.quantity: MaterialStock.quantity - quantity},
            synchronize_session=False,
        )
    )
    if affected != 1:
        raise ValueError(f"{warehouse}库存不足：{item_name}")


def _add_material(
    db: Session, item_id: int, quantity: int, warehouse: str
) -> None:
    row = (
        db.query(MaterialStock)
        .filter(
            MaterialStock.item_id == item_id,
            MaterialStock.warehouse == warehouse,
        )
        .first()
    )
    if row:
        row.quantity += quantity
    else:
        db.add(
            MaterialStock(item_id=item_id, warehouse=warehouse, quantity=quantity)
        )


def _issue_drug_fefo(
    db: Session, order: OutboundOrder, item: OutboundItem, quantity: int, issuer: str
) -> None:
    """近效期先出：未指定批号时，按效期从总库多批次自动分配。"""
    today = date.today()
    rows = (
        db.query(WarehouseStock)
        .filter(
            WarehouseStock.drug_id == item.drug_id,
            WarehouseStock.quantity > 0,
            WarehouseStock.expiry >= today,
        )
        .order_by(WarehouseStock.expiry.asc(), WarehouseStock.id.asc())
        .all()
    )
    available = sum(row.quantity for row in rows)
    if available < quantity:
        raise ValueError(
            f"总库库存不足：{item.name}（可用 {available}，需 {quantity}，已排除过期批次）"
        )

    drug = get_drug(db, item.drug_id)
    remaining = quantity
    target = order.target_name or "药房"
    for row in rows:
        if remaining <= 0:
            break
        take = min(row.quantity, remaining)
        affected = (
            db.query(WarehouseStock)
            .filter(
                WarehouseStock.id == row.id,
                WarehouseStock.quantity >= take,
            )
            .update(
                {WarehouseStock.quantity: WarehouseStock.quantity - take},
                synchronize_session=False,
            )
        )
        if affected != 1:
            raise ValueError(f"总库库存不足：{item.name}")
        _add_drug(db, drug.id, row.batch_no, row.expiry, take, target)
        db.flush()
        for warehouse_name, direction in (("总库", "out"), (target, "in")):
            record_drug(
                db,
                drug,
                batch_no=row.batch_no,
                expiry=row.expiry,
                warehouse=warehouse_name,
                direction=direction,
                quantity=take,
                unit_price=item.unit_price,
                ref_type="outbound",
                ref_id=order.id,
                operator=issuer,
                note=f"出库单 {order.outbound_no}（近效期先出自动分配）",
            )
        remaining -= take


def _issue_item(
    db: Session, order: OutboundOrder, item: OutboundItem, quantity: int, issuer: str
) -> None:
    """按单据类型执行一条明细的出库/退库/报损，并记流水。"""
    target = order.target_name or "药房"

    if (
        item.kind == "drug"
        and order.outbound_type == "requisition"
        and not item.batch_no
    ):
        _issue_drug_fefo(db, order, item, quantity, issuer)
        return

    if item.kind == "drug":
        drug = get_drug(db, item.drug_id)
        expiry = item.expiry

        if order.outbound_type == "scrap":
            expiry = _deduct_drug(db, drug.id, item.batch_no, quantity, "总库", item.name)
            record_drug(
                db, drug, batch_no=item.batch_no, expiry=expiry, warehouse="总库",
                direction="out", quantity=quantity, unit_price=item.unit_price,
                ref_type="scrap", ref_id=order.id, operator=issuer,
                note=f"报损出库 {order.outbound_no}",
            )
            return

        if order.outbound_type == "return":
            expiry = _deduct_drug(db, drug.id, item.batch_no, quantity, target, item.name)
            _add_drug(db, drug.id, item.batch_no, expiry, quantity, "总库")
            db.flush()
            for warehouse_name, direction in ((target, "out"), ("总库", "in")):
                record_drug(
                    db, drug, batch_no=item.batch_no, expiry=expiry,
                    warehouse=warehouse_name, direction=direction, quantity=quantity,
                    unit_price=item.unit_price, ref_type="return", ref_id=order.id,
                    operator=issuer, note=f"退库 {order.outbound_no}",
                )
            return

        expiry = _deduct_drug(db, drug.id, item.batch_no, quantity, "总库", item.name)
        _add_drug(db, drug.id, item.batch_no, expiry, quantity, target)
        db.flush()
        for warehouse_name, direction in (("总库", "out"), (target, "in")):
            record_drug(
                db, drug, batch_no=item.batch_no, expiry=expiry,
                warehouse=warehouse_name, direction=direction, quantity=quantity,
                unit_price=item.unit_price, ref_type="outbound", ref_id=order.id,
                operator=issuer, note=f"出库单 {order.outbound_no}",
            )
        return

    material = get_material_item(db, item.material_id)
    if order.outbound_type == "scrap":
        _deduct_material(db, material.id, quantity, "总库", item.name)
        record_material(
            db, material, warehouse="总库", direction="out", quantity=quantity,
            unit_price=item.unit_price, ref_type="scrap", ref_id=order.id,
            operator=issuer, note=f"报损出库 {order.outbound_no}",
        )
        return

    if order.outbound_type == "return":
        _deduct_material(db, material.id, quantity, target, item.name)
        _add_material(db, material.id, quantity, "总库")
        db.flush()
        for warehouse_name, direction in ((target, "out"), ("总库", "in")):
            record_material(
                db, material, warehouse=warehouse_name, direction=direction,
                quantity=quantity, unit_price=item.unit_price, ref_type="return",
                ref_id=order.id, operator=issuer, note=f"退库 {order.outbound_no}",
            )
        return

    _deduct_material(db, material.id, quantity, "总库", item.name)
    _add_material(db, material.id, quantity, target)
    db.flush()
    for warehouse_name, direction in (("总库", "out"), (target, "in")):
        record_material(
            db, material, warehouse=warehouse_name, direction=direction,
            quantity=quantity, unit_price=item.unit_price, ref_type="outbound",
            ref_id=order.id, operator=issuer, note=f"出库单 {order.outbound_no}",
        )


def issue_outbound(
    db: Session,
    order_id: int,
    issuer: str,
    items: list | None = None,
) -> OutboundOrder:
    """库房出库：支持整单/部分出库；退库与报损按单据类型处理。"""
    order = get_outbound(db, order_id)
    if not order:
        raise ValueError("出库单不存在")
    if order.status not in ("approved", "partially_issued"):
        raise ValueError("仅已审核或部分出库的出库单可以出库")

    requested: dict[int, int] = {}
    if items:
        for entry in items:
            item_id = entry.item_id if hasattr(entry, "item_id") else entry["item_id"]
            quantity = entry.quantity if hasattr(entry, "quantity") else entry["quantity"]
            matched = next((i for i in order.items if i.id == item_id), None)
            if not matched:
                raise ValueError(f"明细不存在：{item_id}")
            requested[item_id] = quantity

    plan: list[tuple] = []
    for item in order.items:
        remaining = item.quantity - item.issued_quantity
        quantity = requested.get(item.id, remaining if not items else 0)
        if quantity < 0:
            raise ValueError("出库数量不能为负")
        if quantity > remaining:
            raise ValueError(f"出库数量超过剩余：{item.name}")
        if quantity > 0:
            plan.append((item, quantity))

    if not plan:
        raise ValueError("本次没有可出库数量")

    try:
        for item, quantity in plan:
            _issue_item(db, order, item, quantity, issuer)
            item.issued_quantity += quantity

        if all(item.issued_quantity >= item.quantity for item in order.items):
            order.status = "issued"
            order.issued_at = datetime.now()
        else:
            order.status = "partially_issued"
        order.issuer = issuer
        db.commit()
    except Exception:
        db.rollback()
        raise
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
        adjustment = StockAdjustment(
            adjust_no=f"AJ{datetime.now():%Y%m%d}{record.id:04d}",
            kind="drug",
            drug_id=drug.id,
            name=drug.name,
            batch_no=data.batch_no,
            expected_quantity=expected,
            actual_quantity=data.actual_quantity,
            diff=diff,
            direction="in" if diff > 0 else "out",
            quantity=abs(diff),
            check_id=record.id,
            operator=checked_by,
            note=f"盘点差异 {diff:+d}",
        )
        db.add(adjustment)
        db.flush()
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
            ref_id=adjustment.id,
            operator=checked_by,
            note=f"调整单 {adjustment.adjust_no}",
        )
    db.commit()
    db.refresh(record)
    return record


def list_adjustments(db: Session, kind: str | None = None) -> list[StockAdjustment]:
    query = db.query(StockAdjustment)
    if kind:
        query = query.filter(StockAdjustment.kind == kind)
    return query.order_by(StockAdjustment.id.desc()).all()


def expiry_alerts(db: Session, days: int = 90) -> dict:
    """效期预警：过期 + 近效期（总库与药房，仅数量>0 的批次）。"""
    today = date.today()
    cutoff = today + timedelta(days=days)
    rows = []

    warehouse_rows = (
        db.query(WarehouseStock)
        .filter(WarehouseStock.quantity > 0, WarehouseStock.expiry <= cutoff)
        .order_by(WarehouseStock.expiry)
        .all()
    )
    for stock in warehouse_rows:
        rows.append(_alert_item(stock.drug, "总库", stock, today))

    pharmacy_rows = (
        db.query(DrugStock)
        .filter(DrugStock.quantity > 0, DrugStock.expiry <= cutoff)
        .order_by(DrugStock.expiry)
        .all()
    )
    for stock in pharmacy_rows:
        rows.append(_alert_item(stock.drug, "药房", stock, today))

    expired = [row for row in rows if row["days_left"] < 0]
    near = [row for row in rows if 0 <= row["days_left"] <= days]
    return {"days": days, "expired": expired, "near_expiry": near}


def _alert_item(drug, warehouse: str, stock, today: date) -> dict:
    days_left = (stock.expiry - today).days
    return {
        "warehouse": warehouse,
        "drug_id": stock.drug_id,
        "name": drug.name if drug else "",
        "spec": drug.spec if drug else "",
        "unit": drug.unit if drug else "",
        "batch_no": stock.batch_no,
        "expiry": stock.expiry,
        "quantity": stock.quantity,
        "days_left": days_left,
        "status": "expired" if days_left < 0 else "near",
    }


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


# ---------- 采购申请（缺货补货） ----------

def _next_purchase_request_no(db: Session) -> str:
    last = db.query(PurchaseRequest.id).order_by(PurchaseRequest.id.desc()).first()
    return f"PR{datetime.now():%Y%m%d}{(last[0] if last else 0) + 1:04d}"


def _stock_available(db: Session, item) -> int:
    if item.kind == "drug" and item.drug_id:
        query = db.query(WarehouseStock).filter(WarehouseStock.drug_id == item.drug_id)
        if item.batch_no:
            query = query.filter(WarehouseStock.batch_no == item.batch_no)
        return sum(row.quantity for row in query.all())
    if item.kind == "material" and item.material_id:
        return sum(
            row.quantity
            for row in db.query(MaterialStock)
            .filter(
                MaterialStock.item_id == item.material_id,
                MaterialStock.warehouse == "总库",
            )
            .all()
        )
    return 0


def create_purchase_request(
    db: Session, data: PurchaseRequestCreate, requester: str = ""
) -> PurchaseRequest:
    if data.supplier_id is not None and not get_supplier(db, data.supplier_id):
        raise ValueError("供应商不存在")
    request = PurchaseRequest(
        request_no=_next_purchase_request_no(db),
        source_type="manual",
        department=data.department,
        requester=requester,
        supplier_id=data.supplier_id,
        note=data.note,
    )
    db.add(request)
    db.flush()
    total = 0.0
    for entry in data.items:
        if entry.kind == "drug":
            drug = get_drug(db, entry.drug_id or 0)
            if not drug:
                raise ValueError("药品不存在")
            name, spec, unit, price = drug.name, "", "", entry.estimated_unit_price or drug.base_price
        else:
            material = get_material_item(db, entry.material_id or 0)
            if not material:
                raise ValueError("物资不存在")
            name, spec, unit, price = (
                material.name,
                material.spec,
                material.unit,
                entry.estimated_unit_price or material.price,
            )
        amount = round(price * entry.quantity, 2)
        total += amount
        db.add(
            PurchaseRequestItem(
                request_id=request.id,
                kind=entry.kind,
                drug_id=entry.drug_id,
                material_id=entry.material_id,
                name=name,
                spec=spec,
                unit=unit,
                quantity=entry.quantity,
                estimated_unit_price=price,
                amount=amount,
                batch_no=entry.batch_no,
                expiry=entry.expiry,
            )
        )
    request.total_amount = round(total, 2)
    db.commit()
    db.refresh(request)
    return request


def create_purchase_request_from_outbound(
    db: Session, order_id: int, requester: str = ""
) -> PurchaseRequest:
    """出库申请缺货时，生成关联采购申请；不把出库单改成采购单。"""
    order = get_outbound(db, order_id)
    if not order:
        raise ValueError("出库单不存在")
    if order.status in ("issued", "cancelled"):
        raise ValueError("该出库单已出库/已取消，不能生成采购申请")
    existing = (
        db.query(PurchaseRequest)
        .filter(
            PurchaseRequest.source_type == "outbound",
            PurchaseRequest.source_id == order.id,
            PurchaseRequest.status.notin_(("rejected", "cancelled", "received")),
        )
        .first()
    )
    if existing:
        return existing
    items = []
    for item in order.items:
        remaining = item.quantity - item.issued_quantity
        available = _stock_available(db, item)
        shortage = remaining - available
        if shortage <= 0:
            continue
        price = item.unit_price
        if not price and item.drug_id:
            drug = get_drug(db, item.drug_id)
            price = drug.base_price if drug else 0
        if not price and item.material_id:
            material = get_material_item(db, item.material_id)
            price = material.price if material else 0
        items.append(
            {
                "kind": item.kind,
                "drug_id": item.drug_id,
                "material_id": item.material_id,
                "name": item.name,
                "spec": item.spec,
                "unit": item.unit,
                "quantity": shortage,
                "price": price,
                "batch_no": item.batch_no,
                "expiry": item.expiry,
            }
        )
    if not items:
        raise ValueError("该出库单没有缺货，不需要采购申请")
    request = PurchaseRequest(
        request_no=_next_purchase_request_no(db),
        source_type="outbound",
        source_id=order.id,
        department=order.target_name,
        requester=requester,
        note=f"出库单 {order.outbound_no} 缺货补货",
    )
    db.add(request)
    db.flush()
    total = 0.0
    for item in items:
        amount = round(item["price"] * item["quantity"], 2)
        total += amount
        db.add(
            PurchaseRequestItem(
                request_id=request.id,
                kind=item["kind"],
                drug_id=item["drug_id"],
                material_id=item["material_id"],
                name=item["name"],
                spec=item["spec"],
                unit=item["unit"],
                quantity=item["quantity"],
                estimated_unit_price=item["price"],
                amount=amount,
                batch_no=item["batch_no"],
                expiry=item["expiry"],
            )
        )
    request.total_amount = round(total, 2)
    order.purchase_request_id = request.id
    db.commit()
    db.refresh(request)
    return request


def list_purchase_requests(
    db: Session, status: str | None = None
) -> list[PurchaseRequest]:
    query = db.query(PurchaseRequest)
    if status:
        query = query.filter(PurchaseRequest.status == status)
    return query.order_by(PurchaseRequest.id.desc()).all()


def get_purchase_request(db: Session, request_id: int) -> PurchaseRequest | None:
    return db.get(PurchaseRequest, request_id)


def approve_purchase_request(
    db: Session, request_id: int, approver: str
) -> PurchaseRequest:
    """机构审核：库房发起，机构管理员批准后才能下单/采购。"""
    request = get_purchase_request(db, request_id)
    if not request:
        raise ValueError("采购申请不存在")
    if request.status != "submitted":
        raise ValueError("只有待审核采购申请可以批准")
    request.status = "approved"
    request.approver = approver
    request.approved_at = datetime.now()
    db.commit()
    db.refresh(request)
    return request


def reject_purchase_request(
    db: Session, request_id: int, data: PurchaseRejectRequest, approver: str
) -> PurchaseRequest:
    request = get_purchase_request(db, request_id)
    if not request:
        raise ValueError("采购申请不存在")
    if request.status != "submitted":
        raise ValueError("只有待审核采购申请可以驳回")
    request.status = "rejected"
    request.approver = approver
    request.rejected_reason = data.reason
    db.commit()
    db.refresh(request)
    return request


def order_purchase_request(
    db: Session, request_id: int, data: PurchaseOrderRequest
) -> PurchaseRequest:
    request = get_purchase_request(db, request_id)
    if not request:
        raise ValueError("采购申请不存在")
    if request.status != "approved":
        raise ValueError("采购申请未批准，不能下单")
    if data.supplier_id is not None and not get_supplier(db, data.supplier_id):
        raise ValueError("供应商不存在")
    request.status = "ordered"
    request.supplier_id = data.supplier_id or request.supplier_id
    request.ordered_at = datetime.now()
    request.note = data.note or request.note
    db.commit()
    db.refresh(request)
    return request


def receive_purchase_request(
    db: Session, request_id: int, data: PurchaseReceiveRequest, operator: str = ""
) -> PurchaseRequest:
    """采购到货入库；支持部分到货，剩余继续待到货。"""
    request = get_purchase_request(db, request_id)
    if not request:
        raise ValueError("采购申请不存在")
    if request.status not in ("approved", "ordered", "partially_received"):
        raise ValueError("采购申请未批准/已结束，不能入库")
    if data.supplier_id is not None and not get_supplier(db, data.supplier_id):
        raise ValueError("供应商不存在")
    for entry in data.items:
        item = next((row for row in request.items if row.id == entry.item_id), None)
        if not item:
            raise ValueError("采购明细不存在")
        remaining = item.quantity - item.received_quantity
        if entry.quantity > remaining:
            raise ValueError(f"到货数量超过未到货数量：{item.name}")
        if item.kind == "drug":
            if not entry.batch_no or not entry.expiry:
                raise ValueError(f"药品到货必须填写批号和效期：{item.name}")
            purchase(
                db,
                PurchaseCreate(
                    drug_id=item.drug_id,
                    batch_no=entry.batch_no,
                    expiry=entry.expiry,
                    quantity=entry.quantity,
                    supplier_id=data.supplier_id or request.supplier_id,
                ),
                purchased_by=operator,
            )
        else:
            from app.modules.materials.schemas import StockInCreate
            from app.modules.materials.service import stock_in

            stock_in(
                db,
                StockInCreate(
                    item_id=item.material_id,
                    warehouse="总库",
                    quantity=entry.quantity,
                ),
            )
        item.received_quantity += entry.quantity
    if request.supplier_id is None:
        request.supplier_id = data.supplier_id
    if all(row.received_quantity >= row.quantity for row in request.items):
        request.status = "received"
        request.received_at = datetime.now()
    else:
        request.status = "partially_received"
    request.note = data.note or request.note
    db.commit()
    db.refresh(request)
    return request
