"""临时脚本：替换 warehouse.service 中的 issue_outbound（支持部分出库/退库/报损）。"""
from pathlib import Path

path = Path("app/modules/warehouse/service.py")
text = path.read_text(encoding="utf-8")
start = text.index("def issue_outbound(")
end = text.index("def cancel_outbound(")

new_code = '''def _deduct_drug(
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


def _issue_item(
    db: Session, order: OutboundOrder, item: OutboundItem, quantity: int, issuer: str
) -> None:
    """按单据类型执行一条明细的出库/退库/报损，并记流水。"""
    target = order.target_name or "药房"
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

    plan: list[tuple[InboundItem, int]] = [] if False else []
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


'''
text = text[:start] + new_code + text[end:]
path.write_text(text, encoding="utf-8")
print("issue_outbound replaced")
