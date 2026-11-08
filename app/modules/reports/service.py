from datetime import date, datetime, time

from sqlalchemy.orm import Session

from app.modules.charges.models import EncounterCharge
from app.modules.encounter.models import Encounter
from app.modules.registration.models import Registration
from app.modules.staff.models import Department, Doctor

_CATEGORY_KEYS = (
    "registration",
    "consultation",
    "drug",
    "lab",
    "imaging",
    "treatment",
)


def department_revenue(
    db: Session, start_date: date | None = None, end_date: date | None = None
) -> list[dict]:
    """科室收入报表：按科室汇总费用明细（已收/已退 + 费用类别）。"""
    query = (
        db.query(
            Department.id,
            Department.name,
            EncounterCharge.charge_type,
            EncounterCharge.status,
            EncounterCharge.amount,
            EncounterCharge.encounter_id,
        )
        .join(Encounter, Encounter.id == EncounterCharge.encounter_id)
        .join(Registration, Registration.id == Encounter.registration_id)
        .join(Doctor, Doctor.id == Registration.doctor_id)
        .join(Department, Department.id == Doctor.department_id)
    )
    if start_date is not None:
        query = query.filter(
            EncounterCharge.created_at >= datetime.combine(start_date, time.min)
        )
    if end_date is not None:
        query = query.filter(
            EncounterCharge.created_at <= datetime.combine(end_date, time.max)
        )

    agg: dict[int, dict] = {}
    for dep_id, dep_name, charge_type, status, amount, encounter_id in query.all():
        item = agg.setdefault(
            dep_id,
            {
                "department_id": dep_id,
                "department_name": dep_name,
                "encounters": set(),
                "paid_amount": 0.0,
                "refunded_amount": 0.0,
                **{f"{key}_amount": 0.0 for key in _CATEGORY_KEYS},
                "other_amount": 0.0,
            },
        )
        if status == "paid":
            item["paid_amount"] = round(item["paid_amount"] + amount, 2)
            item["encounters"].add(encounter_id)
            key = (
                f"{charge_type}_amount"
                if charge_type in _CATEGORY_KEYS
                else "other_amount"
            )
            item[key] = round(item[key] + amount, 2)
        elif status == "refunded":
            item["refunded_amount"] = round(item["refunded_amount"] + amount, 2)

    result = []
    for item in agg.values():
        item["encounter_count"] = len(item.pop("encounters"))
        result.append(item)
    return sorted(result, key=lambda row: row["department_id"])
