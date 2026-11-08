from datetime import date, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.drug.service import get_drug
from app.modules.encounter.service import get_encounter, list_prescription_items
from app.modules.billing.service import get_payment_by_encounter

from .models import Dispense, DrugStock
from .schemas import DispenseRequest, StockInRequest


def stock_in(db: Session, data: StockInRequest) -> DrugStock:
    """入库：同药品同批次累加数量，否则新建批次行。"""
    drug = get_drug(db, data.drug_id)
    if not drug:
        raise ValueError("药品不存在")

    existing = (
        db.query(DrugStock)
        .filter(
            DrugStock.drug_id == data.drug_id,
            DrugStock.batch_no == data.batch_no,
        )
        .first()
    )
    if existing:
        existing.quantity += data.quantity
        db.commit()
        db.refresh(existing)
        return existing

    stock = DrugStock(
        drug_id=data.drug_id,
        batch_no=data.batch_no,
        expiry=data.expiry,
        location=data.location,
        quantity=data.quantity,
    )
    db.add(stock)
    db.commit()
    db.refresh(stock)
    return stock


def get_stock(db: Session, stock_id: int) -> DrugStock | None:
    """按 ID 查询库存批次；不存在时返回 None。"""
    return db.get(DrugStock, stock_id)


def list_stocks(db: Session, drug_id: int | None = None) -> list[DrugStock]:
    """库存批次列表（可按药品过滤）。"""
    query = db.query(DrugStock)
    if drug_id is not None:
        query = query.filter(DrugStock.drug_id == drug_id)
    return query.order_by(DrugStock.drug_id, DrugStock.expiry).all()


def dispense(db: Session, data: DispenseRequest) -> Dispense:
    """发药：就诊已收费且未发药时，按近效期先出扣减库存并记录发药。"""
    encounter = get_encounter(db, data.encounter_id)
    if not encounter:
        raise ValueError("就诊记录不存在")

    payment = get_payment_by_encounter(db, data.encounter_id)
    if not payment or payment.status != "paid":
        raise ValueError("该就诊尚未收费")

    existing = (
        db.query(Dispense).filter(Dispense.encounter_id == data.encounter_id).first()
    )
    if existing:
        raise ValueError("该就诊已发药")

    # 扣库存：逐条处方明细按近效期先出
    for item in list_prescription_items(db, encounter.id):
        deduct_stock(db, item.drug, item.quantity)

    record = Dispense(encounter_id=data.encounter_id)
    db.add(record)
    try:
        db.commit()
    except IntegrityError:
        # 并发发药兜底：dispensations.encounter_id 唯一约束
        db.rollback()
        raise ValueError("该就诊已发药")
    db.refresh(record)
    return record


def deduct_stock(db: Session, drug, quantity: int) -> None:
    """按近效期先出扣减库存（不提交事务）；不足抛 ValueError。

    过期批次自然锁定（不在可选范围）。门诊发药与住院摆药共用。
    """
    stock_rows = (
        db.query(DrugStock)
        .filter(
            DrugStock.drug_id == drug.id,
            DrugStock.quantity > 0,
            DrugStock.expiry >= date.today(),
        )
        .order_by(DrugStock.expiry.asc())
        .all()
    )
    remaining = quantity
    for stock in stock_rows:
        if remaining <= 0:
            break
        take = min(stock.quantity, remaining)
        if take <= 0:
            continue
        # 原子条件扣减：并发下 quantity 不会被扣成负数
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
        remaining -= take
    if remaining > 0:
        raise ValueError(f"库存不足：{drug.name}")


def restore_stock(db: Session, drug, quantity: int) -> None:
    """退药回补库存（不提交事务）：回补到该药最早的批次行。"""
    batch = (
        db.query(DrugStock)
        .filter(DrugStock.drug_id == drug.id)
        .order_by(DrugStock.id)
        .first()
    )
    if not batch:
        raise ValueError("没有可回退的药品批次")
    batch.quantity += quantity


def get_dispense(db: Session, dispense_id: int) -> Dispense | None:
    """按 ID 查询发药记录；不存在时返回 None。"""
    return db.get(Dispense, dispense_id)


def get_dispense_by_encounter(db: Session, encounter_id: int) -> Dispense | None:
    """按就诊查发药记录；不存在时返回 None。"""
    return db.query(Dispense).filter(Dispense.encounter_id == encounter_id).first()


def get_active_dispense_by_encounter(
    db: Session, encounter_id: int
) -> Dispense | None:
    """按就诊查未退回的发药记录（退费拦截用）。"""
    return (
        db.query(Dispense)
        .filter(
            Dispense.encounter_id == encounter_id,
            Dispense.status == "dispensed",
        )
        .first()
    )


def return_dispense(db: Session, dispense_id: int) -> Dispense:
    """门诊退药：库存回补，状态置 returned（原子状态机防并发重复退）。"""
    dispense = get_dispense(db, dispense_id)
    if not dispense:
        raise ValueError("发药记录不存在")
    if dispense.status != "dispensed":
        raise ValueError("该发药记录已退回")

    affected = (
        db.query(Dispense)
        .filter(Dispense.id == dispense_id, Dispense.status == "dispensed")
        .update(
            {
                Dispense.status: "returned",
                Dispense.returned_at: datetime.now(),
            },
            synchronize_session=False,
        )
    )
    if affected != 1:
        raise ValueError("该发药记录已退回")

    for item in list_prescription_items(db, dispense.encounter_id):
        restore_stock(db, item.drug, item.quantity)

    db.commit()
    db.refresh(dispense)
    return dispense
