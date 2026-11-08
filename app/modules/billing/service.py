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

from .models import Payment
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


def refund_payment(db: Session, payment_id: int) -> Payment:
    """退费：已支付且未发药的收费可以退，状态改为 refunded。"""
    payment = get_payment(db, payment_id)
    if not payment:
        raise ValueError("收费记录不存在")

    if payment.status == "refunded":
        raise ValueError("该收费已退费")

    # 延迟导入避免循环依赖（pharmacy.service 也依赖 billing.service）
    from app.modules.pharmacy.service import get_active_dispense_by_encounter

    if get_active_dispense_by_encounter(db, payment.encounter_id):
        raise ValueError("该就诊已发药，不能退费")

    refund_result = refund(
        db,
        payment.channel or "cash",
        payment.channel_trade_no or "",
        payment.self_pay_amount,
    )
    if refund_result["status"] != "success":
        raise ValueError(f"退款失败：{refund_result['message']}")

    payment.status = "refunded"
    # 费用明细同步置为已退
    for charge in list_charges(db, payment.encounter_id):
        if charge.status == "paid":
            charge.status = "refunded"
    db.commit()
    db.refresh(payment)
    return payment


def get_summary(db: Session) -> dict:
    """对账汇总：按收费状态统计笔数和金额。"""
    paid_count = (
        db.query(func.count(Payment.id)).filter(Payment.status == "paid").scalar() or 0
    )
    paid_total = (
        db.query(func.sum(Payment.amount)).filter(Payment.status == "paid").scalar()
        or 0.0
    )
    refunded_count = (
        db.query(func.count(Payment.id))
        .filter(Payment.status == "refunded")
        .scalar()
        or 0
    )
    refunded_total = (
        db.query(func.sum(Payment.amount))
        .filter(Payment.status == "refunded")
        .scalar()
        or 0.0
    )
    return {
        "paid_count": paid_count,
        "paid_total": paid_total,
        "refunded_count": refunded_count,
        "refunded_total": refunded_total,
    }
