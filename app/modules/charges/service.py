from sqlalchemy.orm import Session

from .models import ChargeItem, EncounterCharge
from .schemas import ChargeItemCreate

# 接诊时自动计费的字典编码
REGISTRATION_FEE_CODE = "REG"
CONSULTATION_FEE_CODE = "CONSULT"


def create_item(db: Session, data: ChargeItemCreate) -> ChargeItem:
    """维护收费项目字典：编码唯一。"""
    existing = db.query(ChargeItem).filter(ChargeItem.code == data.code).first()
    if existing:
        raise ValueError("收费项目编码已存在")

    item = ChargeItem(**data.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def get_item(db: Session, item_id: int) -> ChargeItem | None:
    return db.get(ChargeItem, item_id)


def get_item_by_code(db: Session, code: str) -> ChargeItem | None:
    return db.query(ChargeItem).filter(ChargeItem.code == code).first()


def list_items(db: Session, category: str | None = None) -> list[ChargeItem]:
    query = db.query(ChargeItem)
    if category is not None:
        query = query.filter(ChargeItem.category == category)
    return query.order_by(ChargeItem.id).all()


def add_charge(
    db: Session,
    *,
    encounter_id: int,
    source_type: str,
    source_id: int,
    charge_type: str,
    item_name: str,
    quantity: int,
    unit_price: float,
    insurance_ratio: float = 0.7,
    charge_item_id: int | None = None,
    drug_id: int | None = None,
) -> EncounterCharge:
    """新增费用明细（不提交事务，由调用方统一 commit）。

    同一来源（source_type+source_id）只计费一次：已存在则直接返回原明细。
    """
    existing = (
        db.query(EncounterCharge)
        .filter(
            EncounterCharge.source_type == source_type,
            EncounterCharge.source_id == source_id,
        )
        .first()
    )
    if existing:
        return existing

    charge = EncounterCharge(
        encounter_id=encounter_id,
        source_type=source_type,
        source_id=source_id,
        charge_type=charge_type,
        charge_item_id=charge_item_id,
        drug_id=drug_id,
        item_name=item_name,
        quantity=quantity,
        unit_price=unit_price,
        amount=round(quantity * unit_price, 2),
        insurance_ratio=insurance_ratio,
        status="pending",
    )
    db.add(charge)
    db.flush()
    return charge


def add_dict_fee(
    db: Session, *, encounter_id: int, code: str, source_type: str, source_id: int
) -> EncounterCharge | None:
    """按字典编码自动计费（挂号费/诊疗费等）；字典缺失时跳过。"""
    item = get_item_by_code(db, code)
    if not item or not item.active:
        return None
    return add_charge(
        db,
        encounter_id=encounter_id,
        source_type=source_type,
        source_id=source_id,
        charge_type=item.category,
        item_name=item.name,
        quantity=1,
        unit_price=item.price,
        insurance_ratio=item.insurance_ratio,
        charge_item_id=item.id,
    )


def list_charges(db: Session, encounter_id: int) -> list[EncounterCharge]:
    return (
        db.query(EncounterCharge)
        .filter(EncounterCharge.encounter_id == encounter_id)
        .order_by(EncounterCharge.id)
        .all()
    )


def list_pending_charges(db: Session, encounter_id: int) -> list[EncounterCharge]:
    return (
        db.query(EncounterCharge)
        .filter(
            EncounterCharge.encounter_id == encounter_id,
            EncounterCharge.status == "pending",
        )
        .order_by(EncounterCharge.id)
        .all()
    )


def summary(db: Session, encounter_id: int) -> dict:
    charges = list_charges(db, encounter_id)
    totals = {"pending": 0.0, "paid": 0.0, "refunded": 0.0}
    for charge in charges:
        totals[charge.status] = round(totals.get(charge.status, 0.0) + charge.amount, 2)
    return {
        "encounter_id": encounter_id,
        "total_pending": totals.get("pending", 0.0),
        "total_paid": totals.get("paid", 0.0),
        "total_refunded": totals.get("refunded", 0.0),
    }
