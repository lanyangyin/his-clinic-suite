"""院长驾驶舱：期间 KPI、趋势、科室/医生、药品、库存与风险汇总。"""
from datetime import date, datetime, time, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.modules.billing.models import Payment
from app.modules.charges.models import EncounterCharge
from app.modules.encounter.models import Encounter, PrescriptionItem
from app.modules.gsp.service import alerts as gsp_alerts
from app.modules.insurance.workbench import compliance_risks
from app.modules.lis.models import LabRequest
from app.modules.materials.models import MaterialItem, MaterialStock
from app.modules.registration.models import Registration
from app.modules.reports.service import department_revenue
from app.modules.staff.models import Doctor
from app.modules.surgery.models import SurgeryCase
from app.modules.treatment_room.models import TreatmentRoomCase
from app.modules.warehouse.models import PurchaseRequest, WarehouseStock
from app.modules.drug.models import Drug


def resolve_range(start_date: date | None, end_date: date | None) -> tuple[date, date]:
    end = end_date or date.today()
    start = start_date or (end - timedelta(days=29))
    if start > end:
        start, end = end, start
    return start, end


def _dt(start: date, end: date) -> tuple[datetime, datetime]:
    return datetime.combine(start, time.min), datetime.combine(end, time.max)


def _paid_payments(db: Session, start: date, end: date) -> list[Payment]:
    start_dt, end_dt = _dt(start, end)
    return (
        db.query(Payment)
        .filter(
            Payment.status == "paid",
            Payment.created_at >= start_dt,
            Payment.created_at <= end_dt,
        )
        .all()
    )


def _daily_trend(db: Session, start: date, end: date) -> list[dict]:
    start_dt, end_dt = _dt(start, end)
    encounter_rows = (
        db.query(func.date(Encounter.created_at), func.count(Encounter.id))
        .filter(Encounter.created_at >= start_dt, Encounter.created_at <= end_dt)
        .group_by(func.date(Encounter.created_at))
        .all()
    )
    payment_rows = (
        db.query(
            func.date(Payment.created_at),
            func.count(Payment.id),
            func.sum(Payment.amount),
        )
        .filter(
            Payment.status == "paid",
            Payment.created_at >= start_dt,
            Payment.created_at <= end_dt,
        )
        .group_by(func.date(Payment.created_at))
        .all()
    )
    visits = {str(day): count for day, count in encounter_rows}
    payments = {str(day): (count, float(amount or 0)) for day, count, amount in payment_rows}
    result = []
    day = start
    while day <= end:
        key = day.isoformat()
        paid_count, paid_amount = payments.get(key, (0, 0.0))
        result.append(
            {
                "date": key,
                "visits": visits.get(key, 0),
                "paid_count": paid_count,
                "paid_amount": round(paid_amount, 2),
            }
        )
        day += timedelta(days=1)
    return result


def _inventory_alerts(db: Session) -> list[dict]:
    rows = []
    drug_stock = (
        db.query(WarehouseStock.drug_id, func.sum(WarehouseStock.quantity))
        .group_by(WarehouseStock.drug_id)
        .all()
    )
    for drug_id, quantity in drug_stock:
        if (quantity or 0) <= 10:
            drug = db.get(Drug, drug_id)
            rows.append(
                {
                    "kind": "药品",
                    "name": drug.name if drug else f"#{drug_id}",
                    "quantity": int(quantity or 0),
                }
            )
    material_stock = (
        db.query(MaterialStock.item_id, func.sum(MaterialStock.quantity))
        .group_by(MaterialStock.item_id)
        .all()
    )
    for item_id, quantity in material_stock:
        if (quantity or 0) <= 10:
            item = db.get(MaterialItem, item_id)
            rows.append(
                {
                    "kind": "耗材",
                    "name": item.name if item else f"#{item_id}",
                    "quantity": int(quantity or 0),
                }
            )
    return sorted(rows, key=lambda row: row["quantity"])[:20]


def _doctor_workload(db: Session, start: date, end: date) -> list[dict]:
    start_dt, end_dt = _dt(start, end)
    rows = (
        db.query(Doctor.id, Doctor.name, func.count(Encounter.id))
        .join(Registration, Registration.doctor_id == Doctor.id)
        .join(Encounter, Encounter.registration_id == Registration.id)
        .filter(Encounter.created_at >= start_dt, Encounter.created_at <= end_dt)
        .group_by(Doctor.id, Doctor.name)
        .order_by(func.count(Encounter.id).desc())
        .limit(20)
        .all()
    )
    return [
        {"doctor_id": doctor_id, "doctor_name": name, "visits": count}
        for doctor_id, name, count in rows
    ]


def _top_drugs(db: Session, start: date, end: date) -> list[dict]:
    start_dt, end_dt = _dt(start, end)
    rows = (
        db.query(
            PrescriptionItem.drug_id,
            func.sum(PrescriptionItem.quantity),
            func.sum(PrescriptionItem.quantity * PrescriptionItem.unit_price),
        )
        .join(Encounter, Encounter.id == PrescriptionItem.encounter_id)
        .filter(Encounter.created_at >= start_dt, Encounter.created_at <= end_dt)
        .group_by(PrescriptionItem.drug_id)
        .order_by(func.sum(PrescriptionItem.quantity * PrescriptionItem.unit_price).desc())
        .limit(10)
        .all()
    )
    from app.modules.drug.service import get_drug

    return [
        {
            "drug_name": (get_drug(db, drug_id).name if get_drug(db, drug_id) else ""),
            "quantity": int(quantity or 0),
            "amount": round(float(amount or 0), 2),
        }
        for drug_id, quantity, amount in rows
    ]


def executive(db: Session, start_date: date | None = None, end_date: date | None = None) -> dict:
    start, end = resolve_range(start_date, end_date)
    start_dt, end_dt = _dt(start, end)
    payments = _paid_payments(db, start, end)
    revenue = round(sum(p.net_amount for p in payments), 2)
    insurance = round(sum(p.net_amount - p.net_self_pay_amount for p in payments), 2)
    refunds = round(sum(p.refunded_amount for p in payments), 2)
    encounters = (
        db.query(Encounter)
        .filter(Encounter.created_at >= start_dt, Encounter.created_at <= end_dt)
        .all()
    )
    encounter_ids = [row.id for row in encounters]
    charges = (
        db.query(EncounterCharge)
        .filter(EncounterCharge.encounter_id.in_(encounter_ids))
        .all()
        if encounter_ids
        else []
    )
    drug_revenue = round(
        sum(row.amount for row in charges if row.charge_type == "drug" and row.status == "paid"),
        2,
    )
    pending = round(
        sum(row.amount for row in charges if row.status == "pending"),
        2,
    )
    lab_count = (
        db.query(func.count(LabRequest.id))
        .filter(LabRequest.requested_at >= start_dt, LabRequest.requested_at <= end_dt)
        .scalar()
        or 0
    )
    prescription_count = (
        db.query(func.count(PrescriptionItem.id))
        .join(Encounter, Encounter.id == PrescriptionItem.encounter_id)
        .filter(Encounter.created_at >= start_dt, Encounter.created_at <= end_dt)
        .scalar()
        or 0
    )
    surgery_count = (
        db.query(func.count(SurgeryCase.id))
        .filter(
            SurgeryCase.status == "completed",
            SurgeryCase.completed_at >= start_dt,
            SurgeryCase.completed_at <= end_dt,
        )
        .scalar()
        or 0
    )
    treatment_count = (
        db.query(func.count(TreatmentRoomCase.id))
        .filter(
            TreatmentRoomCase.status == "completed",
            TreatmentRoomCase.completed_at >= start_dt,
            TreatmentRoomCase.completed_at <= end_dt,
        )
        .scalar()
        or 0
    )
    purchase_pending = (
        db.query(func.count(PurchaseRequest.id))
        .filter(PurchaseRequest.status.in_(("submitted", "approved", "ordered")))
        .scalar()
        or 0
    )
    gsp = gsp_alerts(db)
    risks = compliance_risks(db, start, end, limit=200)
    paid_count = len(payments)
    return {
        "start_date": start,
        "end_date": end,
        "kpi": {
            "visits": len(encounters),
            "paid_count": paid_count,
            "revenue": revenue,
            "insurance": insurance,
            "self_pay": round(revenue - insurance, 2),
            "refunds": refunds,
            "avg_cost": round(revenue / paid_count, 2) if paid_count else 0,
            "drug_revenue": drug_revenue,
            "drug_ratio": round(drug_revenue / revenue * 100, 1) if revenue else 0,
            "pending_charges": pending,
            "prescriptions": prescription_count,
            "lab_requests": lab_count,
            "surgeries": surgery_count,
            "treatments": treatment_count,
        },
        "trend": _daily_trend(db, start, end),
        "departments": department_revenue(db, start, end),
        "doctors": _doctor_workload(db, start, end),
        "top_drugs": _top_drugs(db, start, end),
        "channels": _channel_summary(payments),
        "inventory_alerts": _inventory_alerts(db),
        "risks": {
            "purchase_pending": purchase_pending,
            "insurance_risks": len(risks),
            "gsp_unqualified": len(gsp["unqualified_acceptances"]),
            "gsp_storage": len(gsp["abnormal_storage"]),
            "gsp_recalls": len(gsp["active_recalls"]),
        },
    }


def _channel_summary(payments: list[Payment]) -> list[dict]:
    labels = {
        "cash": "现金",
        "wechat": "微信",
        "alipay": "支付宝",
        "pos": "POS",
        "insurance_card": "医保卡",
    }
    agg: dict[str, dict] = {}
    for payment in payments:
        row = agg.setdefault(
            payment.channel,
            {"channel": payment.channel, "label": labels.get(payment.channel, payment.channel), "count": 0, "amount": 0.0},
        )
        row["count"] += 1
        row["amount"] = round(row["amount"] + payment.net_amount, 2)
    return sorted(agg.values(), key=lambda row: row["amount"], reverse=True)
