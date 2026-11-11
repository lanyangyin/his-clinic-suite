"""药房零售：OTC 药品/耗材直接销售、扣库存、原单退货。"""
from datetime import date, datetime

from sqlalchemy.orm import Session

from app.modules.drug.service import get_drug
from app.modules.materials.models import MaterialStock
from app.modules.materials.service import get_item as get_material_item
from app.modules.stock_ledger.service import record_drug, record_material

from .models import DrugStock, RetailSale, RetailSaleItem
from .schemas import RetailSaleCreate


def create_retail_sale(db: Session, data: RetailSaleCreate, sold_by: str = "") -> RetailSale:
    sale = RetailSale(
        sale_no="TMP",
        customer_name=data.customer_name.strip(),
        phone=data.phone.strip(),
        channel=data.channel,
        total_amount=0,
        sold_by=sold_by,
    )
    db.add(sale)
    db.flush()

    total = 0.0
    for line in data.items:
        if line.kind == "drug":
            drug = get_drug(db, line.drug_id or 0)
            if not drug:
                raise ValueError("药品不存在")
            if not drug.is_otc:
                raise ValueError(f"「{drug.name}」是处方药，不能直接零售")
            price = line.unit_price if line.unit_price is not None else drug.base_price
            rows = (
                db.query(DrugStock)
                .filter(
                    DrugStock.drug_id == drug.id,
                    DrugStock.quantity > 0,
                    DrugStock.expiry >= date.today(),
                )
                .order_by(DrugStock.expiry)
                .all()
            )
            remaining = line.quantity
            for stock in rows:
                if remaining <= 0:
                    break
                take = min(stock.quantity, remaining)
                affected = (
                    db.query(DrugStock)
                    .filter(DrugStock.id == stock.id, DrugStock.quantity >= take)
                    .update(
                        {DrugStock.quantity: DrugStock.quantity - take},
                        synchronize_session=False,
                    )
                )
                if affected != 1:
                    raise ValueError(f"库存不足：{drug.name}")
                item = RetailSaleItem(
                    sale_id=sale.id,
                    kind="drug",
                    drug_id=drug.id,
                    name=drug.name,
                    spec=drug.spec,
                    unit=drug.unit,
                    batch_no=stock.batch_no,
                    expiry=stock.expiry,
                    warehouse="药房",
                    quantity=take,
                    unit_price=price,
                    amount=round(take * price, 2),
                )
                db.add(item)
                db.flush()
                record_drug(
                    db,
                    drug,
                    batch_no=stock.batch_no,
                    expiry=stock.expiry,
                    warehouse="药房",
                    direction="out",
                    quantity=take,
                    unit_price=price,
                    ref_type="retail_sale",
                    ref_id=sale.id,
                    operator=sold_by,
                    note="药房零售",
                )
                total += item.amount
                remaining -= take
            if remaining > 0:
                raise ValueError(f"库存不足：{drug.name}")
        else:
            material = get_material_item(db, line.material_id or 0)
            if not material:
                raise ValueError("耗材不存在")
            warehouse = line.warehouse or "药房"
            stock = (
                db.query(MaterialStock)
                .filter(
                    MaterialStock.item_id == material.id,
                    MaterialStock.warehouse == warehouse,
                )
                .first()
            )
            if not stock or stock.quantity < line.quantity:
                raise ValueError(f"耗材库存不足：{material.name}（{warehouse}）")
            price = line.unit_price if line.unit_price is not None else material.price
            stock.quantity -= line.quantity
            item = RetailSaleItem(
                sale_id=sale.id,
                kind="material",
                material_id=material.id,
                name=material.name,
                spec=material.spec,
                unit=material.unit,
                warehouse=warehouse,
                quantity=line.quantity,
                unit_price=price,
                amount=round(line.quantity * price, 2),
            )
            db.add(item)
            db.flush()
            record_material(
                db,
                material,
                warehouse=warehouse,
                direction="out",
                quantity=line.quantity,
                unit_price=price,
                ref_type="retail_sale",
                ref_id=sale.id,
                operator=sold_by,
                note="药房零售",
            )
            total += item.amount

    sale.total_amount = round(total, 2)
    sale.sale_no = f"LS{datetime.now():%Y%m%d}{sale.id:04d}"
    db.commit()
    db.refresh(sale)
    return sale


def list_retail_sales(db: Session, limit: int = 100) -> list[RetailSale]:
    return (
        db.query(RetailSale)
        .order_by(RetailSale.id.desc())
        .limit(limit)
        .all()
    )


def get_retail_sale(db: Session, sale_id: int) -> RetailSale | None:
    return db.get(RetailSale, sale_id)


def refund_retail_sale(
    db: Session, sale_id: int, operator: str = "", reason: str = ""
) -> RetailSale:
    sale = db.get(RetailSale, sale_id)
    if not sale:
        raise ValueError("零售单不存在")
    if sale.status != "completed":
        raise ValueError("该零售单已退货")
    for item in sale.items:
        if item.kind == "drug":
            drug = get_drug(db, item.drug_id or 0)
            if not drug:
                continue
            stock = (
                db.query(DrugStock)
                .filter(
                    DrugStock.drug_id == drug.id,
                    DrugStock.batch_no == item.batch_no,
                )
                .first()
            )
            if stock:
                stock.quantity += item.quantity
            else:
                stock = DrugStock(
                    drug_id=drug.id,
                    batch_no=item.batch_no,
                    expiry=item.expiry or date.today(),
                    quantity=item.quantity,
                )
                db.add(stock)
            db.flush()
            record_drug(
                db,
                drug,
                batch_no=item.batch_no,
                expiry=item.expiry,
                warehouse="药房",
                direction="in",
                quantity=item.quantity,
                unit_price=item.unit_price,
                ref_type="retail_refund",
                ref_id=sale.id,
                operator=operator,
                note=reason or "零售退货",
            )
        else:
            material = get_material_item(db, item.material_id or 0)
            if not material:
                continue
            stock = (
                db.query(MaterialStock)
                .filter(
                    MaterialStock.item_id == material.id,
                    MaterialStock.warehouse == item.warehouse,
                )
                .first()
            )
            if stock:
                stock.quantity += item.quantity
            else:
                db.add(
                    MaterialStock(
                        item_id=material.id,
                        warehouse=item.warehouse,
                        quantity=item.quantity,
                    )
                )
            db.flush()
            record_material(
                db,
                material,
                warehouse=item.warehouse,
                direction="in",
                quantity=item.quantity,
                unit_price=item.unit_price,
                ref_type="retail_refund",
                ref_id=sale.id,
                operator=operator,
                note=reason or "零售退货",
            )
    sale.status = "refunded"
    sale.refunded_by = operator
    sale.refunded_at = datetime.now()
    db.commit()
    db.refresh(sale)
    return sale
