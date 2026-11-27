from datetime import datetime

from sqlalchemy.orm import Session

from app.modules.charges.service import add_charge, get_item

from .models import TreatmentOrder
from .schemas import TreatmentOrderCreate


def create_treatment(
    db: Session, encounter_id: int, data: TreatmentOrderCreate, ordered_by: str
) -> TreatmentOrder:
    """医生开治疗单：就诊未关闭、项目有效；开单即计费（同事务）。"""
    from app.modules.encounter.service import get_medical_record, get_encounter

    encounter = get_encounter(db, encounter_id)
    if not encounter:
        raise ValueError("就诊记录不存在")
    existing = (
        db.query(TreatmentOrder)
        .filter(
            TreatmentOrder.encounter_id == encounter.id,
            TreatmentOrder.charge_item_id == data.item_id,
            TreatmentOrder.status == "pending",
        )
        .first()
    )
    if existing:
        raise ValueError("该治疗项目已开立且未执行，请勿重复开单")
    if encounter.status == "closed":
        raise ValueError("就诊已收费，不能再开治疗单")
    if get_medical_record(db, encounter.id) and get_medical_record(db, encounter.id).signed_at:
        raise ValueError("病历已签名，不能再开治疗；请先申请病历修订")
    if encounter.status in ("abandoned", "cancelled"):
        raise ValueError("就诊已放弃，不能再开治疗单")

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
    from app.modules.charges.models import EncounterCharge

    query = db.query(TreatmentOrder)
    if status is not None:
        query = query.filter(TreatmentOrder.status == status)
    rows = query.order_by(TreatmentOrder.id.desc()).all()
    paid_ids = {
        row.source_id
        for row in db.query(EncounterCharge.source_id)
        .filter(
            EncounterCharge.source_type == "treatment",
            EncounterCharge.status.in_(("paid", "partially_refunded")),
        )
        .all()
    }
    for order in rows:
        # 只按本治疗单的费用判断，不能拿同就诊其他已付费用冒充
        order.paid = order.id in paid_ids
    return rows


def execute_treatment(db: Session, order_id: int, executed_by: str) -> TreatmentOrder:
    """护士执行治疗：pending → done（原子状态机，并发只生效一次）。"""
    order = get_treatment(db, order_id)
    if not order:
        raise ValueError("治疗单不存在")
    if order.status != "pending":
        raise ValueError("该治疗单已执行或已取消")
    from app.modules.charges.models import EncounterCharge

    paid_charge = db.query(EncounterCharge).filter(
        EncounterCharge.source_type == "treatment",
        EncounterCharge.source_id == order.id,
        EncounterCharge.status.in_(("paid", "partially_refunded")),
    ).first()
    if not paid_charge:
        raise ValueError("该治疗项目尚未收费，不能执行治疗")

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

    treatment_charges = [
        charge
        for charge in list_charges(db, order.encounter_id)
        if charge.source_type == "treatment" and charge.source_id == order.id
    ]
    if any(charge.status in ("paid", "partially_refunded") for charge in treatment_charges):
        order.status = "dc"
        db.commit()
        db.refresh(order)
        return order
    order.status = "cancelled"
    for charge in treatment_charges:
        charge.status = "cancelled"
    db.commit()
    db.refresh(order)
    return order
