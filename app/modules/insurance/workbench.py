"""医保工作台：对码统计、结算统计、合规风险、事前事中检查。"""
from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from app.modules.billing.models import Payment
from app.modules.charges.models import ChargeItem
from app.modules.drug.models import Drug
from app.modules.encounter.models import Encounter, PrescriptionItem
from app.modules.materials.models import MaterialItem
from app.modules.patient.models import Patient
from app.modules.registration.models import Registration


def _date_end(value: date | None) -> date:
    return value or date.today()


def _date_start(value: date | None, end: date) -> date:
    return value or (end - timedelta(days=30))


def _payment_query(db: Session, start: date, end: date):
    return db.query(Payment).filter(
        Payment.created_at >= datetime.combine(start, datetime.min.time()),
        Payment.created_at < datetime.combine(end + timedelta(days=1), datetime.min.time()),
    )


def _drug_category(drug: Drug) -> str:
    if drug.insurance_match_status != "matched" and not drug.insurance_code:
        return "未对码"
    if drug.insurance_category in ("甲", "乙", "丙"):
        return drug.insurance_category
    return "无等级"


def matching_stats(db: Session) -> dict:
    drugs = db.query(Drug).all()
    by_category: dict[str, int] = {}
    for drug in drugs:
        category = _drug_category(drug)
        by_category[category] = by_category.get(category, 0) + 1
    materials = db.query(MaterialItem).all()
    material_unmatched = sum(1 for row in materials if not row.insurance_code)
    charge_items = db.query(ChargeItem).all()
    drug_unmatched = by_category.get("未对码", 0)
    return {
        "drugs": {
            "total": len(drugs),
            "matched": len(drugs) - drug_unmatched,
            "unmatched": drug_unmatched,
            "by_category": {
                "甲": by_category.get("甲", 0),
                "乙": by_category.get("乙", 0),
                "丙": by_category.get("丙", 0),
                "无等级": by_category.get("无等级", 0),
                "未对码": drug_unmatched,
            },
        },
        "materials": {
            "total": len(materials),
            "matched": len(materials) - material_unmatched,
            "unmatched": material_unmatched,
        },
        "charge_items": {
            "total": len(charge_items),
            # 收费项目尚未建医保贯标字段，按未贯标统计
            "unmatched": len(charge_items),
        },
        "price_limit_configured": False,
    }


def settlement_stats(db: Session, start: date, end: date) -> dict:
    payments = _payment_query(db, start, end).all()
    channels: dict[str, int] = {}
    for payment in payments:
        channels[payment.channel] = channels.get(payment.channel, 0) + 1
    return {
        "payment_count": len(payments),
        "total_amount": round(sum(p.amount for p in payments), 2),
        "insurance_amount": round(sum(p.insurance_amount for p in payments), 2),
        "self_pay_amount": round(sum(p.self_pay_amount for p in payments), 2),
        "refunded_amount": round(sum(p.refunded_amount for p in payments), 2),
        "by_channel": channels,
    }


def compliance_risks(db: Session, start: date, end: date, limit: int = 100) -> list[dict]:
    rows = (
        db.query(PrescriptionItem, Encounter, Patient)
        .join(Encounter, PrescriptionItem.encounter_id == Encounter.id)
        .join(Registration, Encounter.registration_id == Registration.id)
        .join(Patient, Registration.patient_id == Patient.id)
        .filter(
            Encounter.created_at >= datetime.combine(start, datetime.min.time()),
            Encounter.created_at < datetime.combine(end + timedelta(days=1), datetime.min.time()),
        )
        .order_by(PrescriptionItem.id.desc())
        .limit(limit)
        .all()
    )
    risks = []
    for item, encounter, patient in rows:
        drug = item.drug
        category = _drug_category(drug) if drug else "未对码"
        reason = ""
        if category == "未对码":
            reason = "药品未完成医保对码，按自费处理"
        elif category == "丙":
            reason = "丙类药品，医保不予支付"
        if not reason:
            continue
        risks.append(
            {
                "encounter_id": encounter.id,
                "patient_name": patient.name,
                "diagnosis": encounter.diagnosis,
                "drug_name": item.drug_name,
                "category": category,
                "reason": reason,
                "amount": round(item.unit_price * item.quantity, 2),
                "created_at": item.created_at,
            }
        )
    return risks


def encounter_risks(db: Session, encounter_id: int) -> dict | None:
    encounter = db.get(Encounter, encounter_id)
    if not encounter:
        return None
    registration = db.get(Registration, encounter.registration_id)
    patient = db.get(Patient, registration.patient_id) if registration else None
    items = (
        db.query(PrescriptionItem)
        .filter(PrescriptionItem.encounter_id == encounter_id)
        .all()
    )
    risks = []
    for item in items:
        category = _drug_category(item.drug) if item.drug else "未对码"
        reason = ""
        if category == "未对码":
            reason = "药品未完成医保对码，按自费处理"
        elif category == "丙":
            reason = "丙类药品，医保不予支付"
        if reason:
            risks.append(
                {
                    "prescription_item_id": item.id,
                    "drug_name": item.drug_name,
                    "category": category,
                    "reason": reason,
                    "amount": round(item.unit_price * item.quantity, 2),
                }
            )
    return {
        "encounter_id": encounter.id,
        "patient_name": patient.name if patient else "",
        "diagnosis": encounter.diagnosis,
        "passed": not risks,
        "risks": risks,
    }


def workbench(db: Session, start_date: date | None = None, end_date: date | None = None) -> dict:
    end = _date_end(end_date)
    start = _date_start(start_date, end)
    risks = compliance_risks(db, start, end)
    return {
        "start_date": start,
        "end_date": end,
        "matching": matching_stats(db),
        "settlement": settlement_stats(db, start, end),
        "risks": risks,
        "risk_count": len(risks),
        "price_limit_note": "尚未配置医保限价规则；当前只做目录类别/对码检查",
    }
