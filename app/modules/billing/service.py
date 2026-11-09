from datetime import datetime

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.charges.service import list_charges, list_pending_charges
from app.modules.encounter.service import (
    close_encounter,
    get_encounter,
    get_encounter_total,
    list_prescription_items,
)
from app.modules.insurance.adapter import InsuranceUnavailable, settle_payment
from app.modules.payment_gateway.service import CHANNELS, charge as charge_payment, refund

from .models import ChargeRefund, Payment
from .schemas import PaymentCreate


def create_payment(db: Session, data: PaymentCreate) -> Payment:
    """收费：汇总就诊全部待收费用明细，医保按明细比例结算，关闭就诊。"""
    encounter = get_encounter(db, data.encounter_id)
    if not encounter:
        raise ValueError("就诊记录不存在")

    existing = (
        db.query(Payment).filter(Payment.encounter_id == data.encounter_id).first()
    )
    if existing:
        raise ValueError("该就诊已收费")

    charges = list_pending_charges(db, data.encounter_id)
    if not charges:
        raise ValueError("该就诊没有可收费的费用")

    amount = round(sum(c.amount for c in charges), 2)

    # 医保结算：按费用明细逐条计算（服务不可用降级为全额自费）
    lines = [
        {
            "drug_name": c.item_name,
            "total": c.amount,
            "ratio": c.insurance_ratio,
        }
        for c in charges
    ]
    try:
        settle = settle_payment(lines=lines)
        insurance_amount = settle["insurance_amount"]
    except InsuranceUnavailable:
        insurance_amount = 0.0

    channel = data.channel or "cash"
    if channel not in CHANNELS:
        raise ValueError("未知支付通道")
    self_pay = round(amount - insurance_amount, 2)
    result = charge_payment(
        db,
        channel,
        self_pay,
        auth_code=data.auth_code,
        card_no=data.card_no,
        subject=f"门诊收费 就诊{data.encounter_id}",
    )
    if result["status"] != "success":
        raise ValueError(f"支付失败：{result['message']}")

    payment = Payment(
        encounter_id=data.encounter_id,
        amount=amount,
        insurance_amount=insurance_amount,
        channel=channel,
        channel_trade_no=result.get("trade_no", ""),
        channel_status=result.get("channel_status", "success"),
    )
    db.add(payment)
    for charge in charges:
        charge.status = "paid"
    close_encounter(db, encounter)
    try:
        db.flush()
        # 发票票据号（演示：INV + 日期 + 6 位流水）
        payment.invoice_no = f"INV{datetime.now():%Y%m%d}{payment.id:06d}"
        db.commit()
    except IntegrityError:
        # 并发双收兜底：payments.encounter_id 唯一约束
        db.rollback()
        raise ValueError("该就诊已收费")
    db.refresh(payment)
    return payment


def get_payment_by_encounter(db: Session, encounter_id: int) -> Payment | None:
    """按就诊查收费记录；不存在时返回 None。"""
    return db.query(Payment).filter(Payment.encounter_id == encounter_id).first()


def get_payment(db: Session, payment_id: int) -> Payment | None:
    """按 ID 查询收费记录；不存在时返回 None。"""
    return db.get(Payment, payment_id)


def list_payments(
    db: Session, status: str | None = None, encounter_id: int | None = None
) -> list[Payment]:
    """收费记录列表（可按状态/就诊过滤，最新在前）。"""
    query = db.query(Payment)
    if status is not None:
        query = query.filter(Payment.status == status)
    if encounter_id is not None:
        query = query.filter(Payment.encounter_id == encounter_id)
    return query.order_by(Payment.id.desc()).all()


def refund_payment(
    db: Session, payment_id: int, items=None, operator: str = ""
) -> Payment:
    """退费：支持按费用明细/数量部分退费（可只退 1 颗药）。"""
    payment = get_payment(db, payment_id)
    if not payment:
        raise ValueError("收费记录不存在")
    if payment.status == "refunded":
        raise ValueError("该收费已退费")

    # 延迟导入避免循环依赖（pharmacy.service 也依赖 billing.service）
    from app.modules.pharmacy.service import get_active_dispense_by_encounter

    dispensed = bool(get_active_dispense_by_encounter(db, payment.encounter_id))
    if dispensed and not items:
        raise ValueError("该就诊已发药，不能退费")
    charges = {
        charge.id: charge for charge in list_charges(db, payment.encounter_id)
    }

    plan: list[tuple] = []
    if items is None:
        for charge in charges.values():
            remaining = charge.quantity - charge.refunded_quantity
            if remaining > 0 and charge.status in ("paid", "partially_refunded"):
                plan.append((charge, remaining))
    else:
        requested: dict[int, int] = {}
        for item in items:
            charge_id = item.charge_id if hasattr(item, "charge_id") else item["charge_id"]
            quantity = item.quantity if hasattr(item, "quantity") else item["quantity"]
            requested[charge_id] = requested.get(charge_id, 0) + quantity
        for charge_id, quantity in requested.items():
            charge = charges.get(charge_id)
            if not charge:
                raise ValueError("费用明细不存在或不属于该收费")
            remaining = charge.quantity - charge.refunded_quantity
            if quantity > remaining:
                raise ValueError(f"退款数量超过可退数量：{charge.item_name}")
            if dispensed and charge.charge_type == "drug":
                raise ValueError("该就诊已发药，请先退药后再退费")
            plan.append((charge, quantity))

    if not plan:
        raise ValueError("没有可退费用")

    total_amount = 0.0
    total_insurance = 0.0
    for charge, quantity in plan:
        amount = round(charge.unit_price * quantity, 2)
        total_amount += amount
        total_insurance += round(amount * charge.insurance_ratio, 2)
    total_amount = round(total_amount, 2)
    total_insurance = round(total_insurance, 2)
    total_self_pay = round(total_amount - total_insurance, 2)

    if total_self_pay > 0:
        refund_result = refund(
            db,
            payment.channel or "cash",
            payment.channel_trade_no or "",
            total_self_pay,
        )
        if refund_result["status"] != "success":
            raise ValueError(f"退款失败：{refund_result['message']}")

    refund_no = f"RF{datetime.now():%Y%m%d%H%M%S}{payment.id:04d}"
    for charge, quantity in plan:
        amount = round(charge.unit_price * quantity, 2)
        insurance = round(amount * charge.insurance_ratio, 2)
        charge.refunded_quantity += quantity
        charge.status = (
            "refunded"
            if charge.refunded_quantity >= charge.quantity
            else "partially_refunded"
        )
        db.add(
            ChargeRefund(
                payment_id=payment.id,
                charge_id=charge.id,
                quantity=quantity,
                amount=amount,
                insurance_amount=insurance,
                self_pay_amount=round(amount - insurance, 2),
                refund_no=refund_no,
                channel=payment.channel or "cash",
                channel_trade_no=payment.channel_trade_no or "",
                operator=operator,
            )
        )

    payment.refunded_amount = round(payment.refunded_amount + total_amount, 2)
    payment.refunded_insurance_amount = round(
        payment.refunded_insurance_amount + total_insurance, 2
    )
    all_refunded = all(
        charge.refunded_quantity >= charge.quantity for charge in charges.values()
    )
    payment.status = "refunded" if all_refunded else "partially_refunded"
    db.commit()
    db.refresh(payment)
    return payment


def get_summary(db: Session) -> dict:
    """对账汇总：按收费状态统计笔数和金额（部分退费按净额统计）。"""
    paid_filter = Payment.status.in_(["paid", "partially_refunded"])
    paid_count = (
        db.query(func.count(Payment.id)).filter(paid_filter).scalar() or 0
    )
    paid_total = (
        db.query(func.sum(Payment.amount - Payment.refunded_amount))
        .filter(paid_filter)
        .scalar()
        or 0.0
    )
    refunded_filter = Payment.refunded_amount > 0
    refunded_count = (
        db.query(func.count(Payment.id)).filter(refunded_filter).scalar() or 0
    )
    refunded_total = (
        db.query(func.sum(Payment.refunded_amount))
        .filter(refunded_filter)
        .scalar()
        or 0.0
    )
    return {
        "paid_count": paid_count,
        "paid_total": round(paid_total, 2),
        "refunded_count": refunded_count,
        "refunded_total": round(refunded_total, 2),
    }
