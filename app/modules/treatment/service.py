from datetime import datetime

from sqlalchemy.orm import Session

from app.modules.charges.service import add_charge, get_item

from .models import TreatmentOrder
from .schemas import TreatmentOrderCreate


def create_treatment(
    db: Session, encounter_id: int, data: TreatmentOrderCreate, ordered_by: str
) -> TreatmentOrder:
    """医生开治疗单：就诊未关闭、项目有效；开单即计费（同事务）。"""
    from app.modules.encounter.service import get_encounter

    encounter = get_encounter(db, encounter_id)
    if not encounter:
        raise ValueError("就诊记录不存在")
    if encounter.status == "closed":
        raise ValueError("就诊已收费，不能再开治疗单")

    item = get_item(db, data.item_id)
    if not item or not item.active:
        raise ValueError("治疗项目不存在或已停用")
    if item.category not in ("treatment", "other"):
        raise ValueError("该项目不是治疗类收费项目")

    order = TreatmentOrder(
        encounter_id=encounter_id,
        charge_item_id=item.id,
        item_name=item.name,
        quantity=data.quantity,
        note=data.note,
        status="pending",
        ordered_by=ordered_by,
    )
    db.add(order)
    db.flush()

    add_charge(
        db,
        encounter_id=encounter_id,
        source_type="treatment",
        source_id=order.id,
        charge_type="treatment",
        item_name=item.name,
        quantity=data.quantity,
        unit_price=item.price,
        insurance_ratio=item.insurance_ratio,
        charge_item_id=item.id,
    )

    db.commit()
    db.refresh(order)
    return order


def get_treatment(db: Session, order_id: int) -> TreatmentOrder | None:
    return db.get(TreatmentOrder, order_id)


def list_treatments(db: Session, encounter_id: int) -> list[TreatmentOrder]:
    return (
        db.query(TreatmentOrder)
        .filter(TreatmentOrder.encounter_id == encounter_id)
        .order_by(TreatmentOrder.id)
        .all()
    )


def list_all_treatments(
    db: Session, status: str | None = None
) -> list[TreatmentOrder]:
    """全部治疗单（可按状态过滤，最新在前）。"""
    query = db.query(TreatmentOrder)
    if status is not None:
        query = query.filter(TreatmentOrder.status == status)
    return query.order_by(TreatmentOrder.id.desc()).all()


def execute_treatment(db: Session, order_id: int, executed_by: str) -> TreatmentOrder:
    """护士执行治疗：pending → done（原子状态机，并发只生效一次）。"""
    order = get_treatment(db, order_id)
    if not order:
        raise ValueError("治疗单不存在")
    if order.status != "pending":
        raise ValueError("该治疗单已执行或已取消")

    affected = (
        db.query(TreatmentOrder)
        .filter(TreatmentOrder.id == order_id, TreatmentOrder.status == "pending")
        .update(
            {
                TreatmentOrder.status: "done",
                TreatmentOrder.executed_by: executed_by,
                TreatmentOrder.executed_at: datetime.now(),
            },
            synchronize_session=False,
        )
    )
    if affected != 1:
        raise ValueError("该治疗单已执行或已取消")
    db.commit()
    db.refresh(order)
    return order


def cancel_treatment(db: Session, order_id: int) -> TreatmentOrder:
    """取消未执行的治疗单（已计费明细同步置退款）。"""
    order = get_treatment(db, order_id)
    if not order:
        raise ValueError("治疗单不存在")
    if order.status != "pending":
        raise ValueError("仅待执行的治疗单可以取消")

    from app.modules.charges.service import list_charges

    order.status = "cancelled"
    for charge in list_charges(db, order.encounter_id):
        if charge.source_type == "treatment" and charge.source_id == order.id:
            charge.status = "refunded"
    db.commit()
    db.refresh(order)
    return order
