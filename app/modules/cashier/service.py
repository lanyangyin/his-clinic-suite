"""收费员交班与门诊日结。"""
from datetime import date, datetime, time

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.modules.billing.models import ChargeRefund, Payment
from app.modules.charges.models import EncounterCharge

from .models import CashierShift
from .schemas import ShiftClose, ShiftOpen

CHANNEL_LABELS = {
    "cash": "现金",
    "wechat": "微信",
    "alipay": "支付宝",
    "pos": "POS",
    "insurance_card": "医保卡",
}


def open_shift(db: Session, cashier: str, data: ShiftOpen) -> CashierShift:
    existing = (
        db.query(CashierShift)
        .filter(CashierShift.cashier == cashier, CashierShift.status == "open")
        .first()
    )
    if existing:
        raise ValueError("当前已有未交班记录")
    shift = CashierShift(
        shift_no="TMP",
        cashier=cashier,
        opening_float=data.opening_float,
        note=data.note,
    )
    db.add(shift)
    db.flush()
    shift.shift_no = f"CS{datetime.now():%Y%m%d}{shift.id:04d}"
    db.commit()
    db.refresh(shift)
    return shift


def close_shift(db: Session, shift_id: int, cashier: str, data: ShiftClose) -> CashierShift:
    shift = db.get(CashierShift, shift_id)
    if not shift:
        raise ValueError("交班记录不存在")
    if shift.cashier != cashier:
        raise ValueError("不能为其他收费员交班")
    if shift.status != "open":
        raise ValueError("该交班已结束")
    now = datetime.now()
    payments = (
        db.query(Payment)
        .filter(
            Payment.created_by == cashier,
            Payment.channel == "cash",
            Payment.created_at >= shift.opened_at,
            Payment.created_at <= now,
        )
        .all()
    )
    refunds = (
        db.query(ChargeRefund)
        .filter(
            ChargeRefund.operator == cashier,
            ChargeRefund.channel == "cash",
            ChargeRefund.created_at >= shift.opened_at,
            ChargeRefund.created_at <= now,
        )
        .all()
    )
    cash_in = sum(payment.net_amount for payment in payments)
    cash_out = sum(refund.amount for refund in refunds)
    expected = round(shift.opening_float + cash_in - cash_out, 2)
    shift.closed_at = now
    shift.counted_cash = data.counted_cash
    shift.expected_cash = expected
    shift.difference = round(data.counted_cash - expected, 2)
    shift.status = "closed"
    shift.note = data.note or shift.note
    db.commit()
    db.refresh(shift)
    return shift


def list_shifts(db: Session, day: date | None = None, cashier: str | None = None) -> list[CashierShift]:
    query = db.query(CashierShift)
    if day:
        start = datetime.combine(day, time.min)
        end = datetime.combine(day, time.max)
        query = query.filter(
            CashierShift.opened_at >= start, CashierShift.opened_at <= end
        )
    if cashier:
        query = query.filter(CashierShift.cashier == cashier)
    return query.order_by(CashierShift.id.desc()).all()


def _daily_shifts(db: Session, day: date, cashier: str | None) -> list[CashierShift]:
    """日结列表：当天记录 + 跨天仍未交班的当前开班记录。"""
    rows = list_shifts(db, day, cashier)
    if day != date.today():
        return rows
    query = db.query(CashierShift).filter(CashierShift.status == "open")
    if cashier:
        query = query.filter(CashierShift.cashier == cashier)
    existing = {row.id for row in rows}
    for row in query.order_by(CashierShift.id.desc()).all():
        if row.id not in existing:
            rows.insert(0, row)
    return rows


def daily(db: Session, day: date | None = None, cashier: str | None = None) -> dict:
    day = day or date.today()
    start = datetime.combine(day, time.min)
    end = datetime.combine(day, time.max)
    payment_query = db.query(Payment).filter(
        Payment.created_at >= start, Payment.created_at <= end
    )
    refund_query = db.query(ChargeRefund).filter(
        ChargeRefund.created_at >= start, ChargeRefund.created_at <= end
    )
    if cashier:
        payment_query = payment_query.filter(Payment.created_by == cashier)
        refund_query = refund_query.filter(ChargeRefund.operator == cashier)
    payments = payment_query.all()
    refunds = refund_query.all()
    channels: dict[str, dict] = {}
    for payment in payments:
        row = channels.setdefault(
            payment.channel,
            {
                "channel": payment.channel,
                "label": CHANNEL_LABELS.get(payment.channel, payment.channel),
                "count": 0,
                "amount": 0.0,
                "insurance": 0.0,
                "self_pay": 0.0,
                "refunded": 0.0,
            },
        )
        row["count"] += 1
        row["amount"] = round(row["amount"] + payment.amount, 2)
        row["insurance"] = round(row["insurance"] + payment.insurance_amount, 2)
        row["self_pay"] = round(row["self_pay"] + payment.self_pay_amount, 2)
        row["refunded"] = round(row["refunded"] + payment.refunded_amount, 2)
    pending_amount = (
        db.query(func.coalesce(func.sum(EncounterCharge.amount), 0))
        .filter(EncounterCharge.status == "pending")
        .scalar()
        or 0
    )
    total_amount = sum(payment.amount for payment in payments)
    total_insurance = sum(payment.insurance_amount for payment in payments)
    total_refunded = sum(payment.refunded_amount for payment in payments)
    return {
        "date": day,
        "payment_count": len(payments),
        "amount": round(total_amount, 2),
        "insurance": round(total_insurance, 2),
        "self_pay": round(total_amount - total_insurance, 2),
        "refunded": round(total_refunded, 2),
        "net": round(total_amount - total_refunded, 2),
        "refund_count": len(refunds),
        "refund_amount": round(sum(row.amount for row in refunds), 2),
        "pending_amount": round(float(pending_amount), 2),
        "channels": sorted(channels.values(), key=lambda row: row["amount"], reverse=True),
        "shifts": _daily_shifts(db, day, cashier),
        "scope": cashier or "all",
    }
