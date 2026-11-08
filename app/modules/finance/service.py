from datetime import date, datetime, time

from sqlalchemy.orm import Session

from app.modules.billing.models import Payment
from app.modules.inpatient.models import InpatientCharge

from .models import FinanceClosure
from .schemas import DailyCloseRequest


def _day_range(day: date) -> tuple[datetime, datetime]:
    return (
        datetime.combine(day, time.min),
        datetime.combine(day, time.max),
    )


def _month_range(month: str) -> tuple[datetime, datetime]:
    year, mon = (int(part) for part in month.split("-"))
    start = datetime(year, mon, 1)
    end = datetime(year + (mon == 12), (mon % 12) + 1, 1)
    return start, end


def daily_close(db: Session, data: DailyCloseRequest, closed_by: str = "") -> FinanceClosure:
    """日结：汇总当日门诊收费与住院费用，生成日结单（同日唯一）。"""
    existing = (
        db.query(FinanceClosure)
        .filter(FinanceClosure.close_date == data.close_date)
        .first()
    )
    if existing:
        raise ValueError("该日已日结")

    start, end = _day_range(data.close_date)
    payments = (
        db.query(Payment)
        .filter(Payment.created_at >= start, Payment.created_at <= end)
        .all()
    )
    charges = (
        db.query(InpatientCharge)
        .filter(
            InpatientCharge.created_at >= start,
            InpatientCharge.created_at <= end,
        )
        .all()
    )

    paid = [p for p in payments if p.status == "paid"]
    refunded = [p for p in payments if p.status == "refunded"]

    closure = FinanceClosure(
        close_date=data.close_date,
        outpatient_paid_count=len(paid),
        outpatient_paid_amount=round(sum(p.amount for p in paid), 2),
        outpatient_refunded_count=len(refunded),
        outpatient_refunded_amount=round(sum(p.amount for p in refunded), 2),
        insurance_amount=round(sum(p.insurance_amount for p in paid), 2),
        inpatient_charge_count=len(charges),
        inpatient_charge_amount=round(sum(c.amount for c in charges), 2),
        closed_by=closed_by,
    )
    db.add(closure)
    db.commit()
    db.refresh(closure)
    return closure


def get_closure(db: Session, close_date: date) -> FinanceClosure | None:
    return (
        db.query(FinanceClosure).filter(FinanceClosure.close_date == close_date).first()
    )


def list_closures(db: Session, limit: int = 100) -> list[FinanceClosure]:
    return (
        db.query(FinanceClosure)
        .order_by(FinanceClosure.close_date.desc())
        .limit(limit)
        .all()
    )


def monthly_summary(db: Session, month: str) -> dict:
    """月汇总：实时统计当月门诊/住院收入，并返回已日结天数。"""
    start, end = _month_range(month)
    payments = (
        db.query(Payment)
        .filter(Payment.created_at >= start, Payment.created_at < end)
        .all()
    )
    charges = (
        db.query(InpatientCharge)
        .filter(
            InpatientCharge.created_at >= start, InpatientCharge.created_at < end
        )
        .all()
    )
    paid = [p for p in payments if p.status == "paid"]
    refunded = [p for p in payments if p.status == "refunded"]
    closed_days = (
        db.query(FinanceClosure)
        .filter(
            FinanceClosure.close_date >= start.date(),
            FinanceClosure.close_date < end.date(),
        )
        .count()
    )

    return {
        "month": month,
        "outpatient_paid_count": len(paid),
        "outpatient_paid_amount": round(sum(p.amount for p in paid), 2),
        "outpatient_refunded_count": len(refunded),
        "outpatient_refunded_amount": round(sum(p.amount for p in refunded), 2),
        "insurance_amount": round(sum(p.insurance_amount for p in paid), 2),
        "inpatient_charge_count": len(charges),
        "inpatient_charge_amount": round(sum(c.amount for c in charges), 2),
        "closed_days": closed_days,
    }
