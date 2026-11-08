from datetime import date, datetime, time, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.modules.billing.models import Payment
from app.modules.drug.service import get_drug
from app.modules.encounter.models import Encounter, PrescriptionItem
from app.modules.inpatient.models import Admission
from app.modules.lis.models import LabRequest
from app.modules.pacs.models import ImagingRequest
from app.modules.patient.models import Patient
from app.modules.pharmacy.models import Dispense
from app.modules.registration.models import Registration


def _today_range() -> tuple[datetime, datetime]:
    today = date.today()
    return datetime.combine(today, time.min), datetime.combine(today, time.max)


def overview(db: Session) -> dict:
    """院长看板：总量与今日关键指标（仅有时间戳的表可算今日）。"""
    start, end = _today_range()

    payments = (
        db.query(Payment)
        .filter(Payment.created_at >= start, Payment.created_at <= end)
        .all()
    )
    paid = [p for p in payments if p.status == "paid"]
    refunded = [p for p in payments if p.status == "refunded"]

    return {
        "patients_total": db.query(func.count(Patient.id)).scalar() or 0,
        "registrations_total": db.query(func.count(Registration.id)).scalar() or 0,
        "encounters_total": db.query(func.count(Encounter.id)).scalar() or 0,
        "admissions_active": (
            db.query(func.count(Admission.id))
            .filter(Admission.status == "in")
            .scalar()
            or 0
        ),
        "dispenses_total": db.query(func.count(Dispense.id)).scalar() or 0,
        "today_paid_count": len(paid),
        "today_paid_amount": round(sum(p.amount for p in paid), 2),
        "today_refunded_count": len(refunded),
        "today_refunded_amount": round(sum(p.amount for p in refunded), 2),
        "today_insurance_amount": round(sum(p.insurance_amount for p in paid), 2),
        "today_lab_requests": (
            db.query(func.count(LabRequest.id))
            .filter(LabRequest.requested_at >= start, LabRequest.requested_at <= end)
            .scalar()
            or 0
        ),
        "today_imaging_requests": (
            db.query(func.count(ImagingRequest.id))
            .filter(
                ImagingRequest.requested_at >= start,
                ImagingRequest.requested_at <= end,
            )
            .scalar()
            or 0
        ),
        "today_admissions_in": (
            db.query(func.count(Admission.id))
            .filter(Admission.admitted_at >= start, Admission.admitted_at <= end)
            .scalar()
            or 0
        ),
        "today_discharges": (
            db.query(func.count(Admission.id))
            .filter(
                Admission.discharged_at >= start, Admission.discharged_at <= end
            )
            .scalar()
            or 0
        ),
    }


def revenue_trend(db: Session, days: int = 7) -> list[dict]:
    """近 N 天门诊收入趋势（按日聚合已支付收费）。"""
    end_day = date.today()
    start_day = end_day - timedelta(days=days - 1)
    rows = (
        db.query(
            func.date(Payment.created_at).label("day"),
            func.count(Payment.id).label("cnt"),
            func.sum(Payment.amount).label("amount"),
        )
        .filter(
            Payment.status == "paid",
            Payment.created_at >= datetime.combine(start_day, time.min),
        )
        .group_by(func.date(Payment.created_at))
        .all()
    )
    by_day = {row.day: (row.cnt, float(row.amount or 0)) for row in rows}

    result = []
    for offset in range(days):
        day = (start_day + timedelta(days=offset)).isoformat()
        cnt, amount = by_day.get(day, (0, 0.0))
        result.append(
            {"date": day, "paid_count": cnt, "paid_amount": round(amount, 2)}
        )
    return result


def top_diagnoses(db: Session, limit: int = 5) -> list[dict]:
    """诊断 Top N（全量统计）。"""
    rows = (
        db.query(Encounter.diagnosis, func.count(Encounter.id).label("cnt"))
        .filter(Encounter.diagnosis != "")
        .group_by(Encounter.diagnosis)
        .order_by(func.count(Encounter.id).desc())
        .limit(limit)
        .all()
    )
    return [{"diagnosis": row.diagnosis, "count": row.cnt} for row in rows]


def top_drugs(db: Session, limit: int = 5) -> list[dict]:
    """用药 Top N：按处方明细数量合计（全量统计）。"""
    rows = (
        db.query(
            PrescriptionItem.drug_id,
            func.sum(PrescriptionItem.quantity).label("qty"),
        )
        .group_by(PrescriptionItem.drug_id)
        .order_by(func.sum(PrescriptionItem.quantity).desc())
        .limit(limit)
        .all()
    )
    result = []
    for row in rows:
        drug = get_drug(db, row.drug_id)
        result.append(
            {
                "drug_id": row.drug_id,
                "drug_name": drug.name if drug else "",
                "quantity": int(row.qty or 0),
            }
        )
    return result
