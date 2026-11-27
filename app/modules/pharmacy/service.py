from datetime import date, datetime
import secrets
import string

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import settings
from app.modules.drug.service import get_drug
from app.modules.encounter.models import Encounter
from app.modules.encounter.service import (
    get_encounter,
    list_dispensable_prescription_items,
    list_prescription_items,
)
from app.modules.billing.models import Payment
from app.modules.billing.service import get_payment_by_encounter
from app.modules.patient.models import Patient
from app.modules.registration.models import Registration
from app.modules.stock_ledger.service import record_drug

from .models import Dispense, DispenseItem, DrugStock, PharmacyCall, PharmacyPickupCode
from .schemas import DispenseRequest, StockInRequest


def stock_in(db: Session, data: StockInRequest) -> DrugStock:
    """入库：同药同批必须同效期；过期药品禁止入库。"""
    drug = get_drug(db, data.drug_id)
    if not drug:
        raise ValueError("药品不存在")
    from datetime import date as _date

    if data.expiry < _date.today():
        raise ValueError("不能将已过期药品入库")

    existing = (
        db.query(DrugStock)
        .filter(
            DrugStock.drug_id == data.drug_id,
            DrugStock.batch_no == data.batch_no,
        )
        .first()
    )
    if existing and existing.expiry != data.expiry:
        raise ValueError("同批号已存在不同效期，请使用不同批号或先核对库存")
    if existing:
        existing.quantity += data.quantity
        db.flush()
        record_drug(
            db,
            drug,
            batch_no=data.batch_no,
            expiry=data.expiry,
            warehouse="药房",
            direction="in",
            quantity=data.quantity,
            unit_price=drug.base_price,
            ref_type="stock_in",
            ref_id=existing.id,
        )
        db.commit()
        db.refresh(existing)
        return existing

    stock = DrugStock(
        drug_id=data.drug_id,
        batch_no=data.batch_no,
        expiry=data.expiry,
        location=data.location,
        quantity=data.quantity,
    )
    db.add(stock)
    db.flush()
    record_drug(
        db,
        drug,
        batch_no=data.batch_no,
        expiry=data.expiry,
        warehouse="药房",
        direction="in",
        quantity=data.quantity,
        unit_price=drug.base_price,
        ref_type="stock_in",
        ref_id=stock.id,
    )
    db.commit()
    db.refresh(stock)
    return stock


def get_stock(db: Session, stock_id: int) -> DrugStock | None:
    """按 ID 查询库存批次；不存在时返回 None。"""
    return db.get(DrugStock, stock_id)


def list_stocks(db: Session, drug_id: int | None = None) -> list[DrugStock]:
    """库存批次列表（可按药品过滤）。"""
    query = db.query(DrugStock)
    if drug_id is not None:
        query = query.filter(DrugStock.drug_id == drug_id)
    return query.order_by(DrugStock.drug_id, DrugStock.expiry).all()


def dispense(db: Session, data: DispenseRequest, operator: str = "") -> Dispense:
    """发药：就诊已收费且未发药时，按近效期先出扣减库存并记录发药。"""
    encounter = get_encounter(db, data.encounter_id)
    if not encounter:
        raise ValueError("就诊记录不存在")
    registration = db.get(Registration, encounter.registration_id) if encounter else None
    patient_id = registration.patient_id if registration else None

    payment = get_payment_by_encounter(db, data.encounter_id)
    if not payment or payment.status not in ("paid", "partially_refunded"):
        raise ValueError("该就诊尚未收费")
    from app.modules.charges.models import EncounterCharge

    drug_charges = (
        db.query(EncounterCharge)
        .filter(
            EncounterCharge.encounter_id == data.encounter_id,
            EncounterCharge.charge_type == "drug",
            EncounterCharge.status.in_(("paid", "partially_refunded")),
        )
        .all()
    )
    if not drug_charges:
        raise ValueError("该就诊药品费用尚未收费")
    if any(getattr(row, "refunded_quantity", 0) > 0 for row in drug_charges):
        raise ValueError("药品费用已部分退费，不能按原处方整方发药；请先处理处方")

    existing = (
        db.query(Dispense)
        .filter(
            Dispense.encounter_id == data.encounter_id,
            Dispense.status.in_(("dispensed", "partially_returned")),
        )
        .first()
    )
    if existing:
        raise ValueError("该就诊已发药")

    if getattr(settings, "REQUIRE_PRESCRIPTION_REVIEW", True):
        from app.modules.encounter.models import Prescription

        pending = (
            db.query(Prescription)
            .filter(
                Prescription.encounter_id == data.encounter_id,
                Prescription.type != "tcm_herb",
                Prescription.status.in_(("pending_review", "dispensing")),
            )
            .count()
        )
        if pending:
            raise ValueError("存在未通过药师审核的处方，不能发药")

    pickup = None
    require_pickup = bool(getattr(settings, "PHARMACY_REQUIRE_PICKUP_CODE", True))
    if require_pickup and not data.pickup_code.strip():
        raise ValueError("请扫描或输入取药码")
    if require_pickup and not data.receiver_name.strip():
        raise ValueError("请填写取药人姓名")
    if data.pickup_code.strip():
        pickup = (
            db.query(PharmacyPickupCode)
            .filter(PharmacyPickupCode.code == data.pickup_code.strip().upper())
            .first()
        )
        if not pickup:
            raise ValueError("取药码不存在")
        if pickup.encounter_id != data.encounter_id:
            raise ValueError("取药码与就诊不匹配")
        if pickup.used_at is not None:
            raise ValueError("取药码已使用")

    from app.modules.encounter.models import Prescription

    headers = (
        db.query(Prescription)
        .filter(
            Prescription.encounter_id == data.encounter_id,
            Prescription.type != "tcm_herb",
            Prescription.status == "approved",
        )
        .all()
    )
    record = Dispense(encounter_id=data.encounter_id)
    record.verified_by = operator
    record.verified_at = datetime.now()
    record.note = data.note
    record.receiver_name = data.receiver_name.strip()
    record.receiver_relation = data.receiver_relation or "本人"
    if record.receiver_name:
        record.signed_at = datetime.now()
    db.add(record)
    try:
        db.flush()
    except IntegrityError:
        # 并发发药兜底：dispensations.encounter_id 唯一约束
        db.rollback()
        raise ValueError("该就诊已发药")

    # 扣库存：逐条处方明细按近效期先出，并落实际发药明细/批次
    dispense_items = list_dispensable_prescription_items(db, encounter.id)
    if not dispense_items:
        raise ValueError("没有已审方通过、可发药的处方明细")
    special = [
        item for item in dispense_items
        if getattr(item.drug, "high_alert", False) or getattr(item.drug, "controlled_level", "")
    ]
    if special:
        witness = data.witness.strip()
        if not witness:
            raise ValueError("高危/麻精药品发药必须填写第二见证人")
        if witness.strip().lower() == (operator or "").strip().lower():
            raise ValueError("第二见证人不能与发药人相同")
        record.witness = witness
    for header in headers:
        header.status = "dispensing"
        header.updated_at = datetime.now()
    for item in dispense_items:
        allocations = deduct_stock(
            db,
            item.drug,
            item.quantity,
            ref_type="dispense",
            ref_id=record.id,
            operator=operator,
        )
        for batch_no, expiry, quantity in allocations or []:
            if getattr(item.drug, "controlled_level", ""):
                from app.modules.narcotic.service import record_issue

                record_issue(
                    db,
                    drug=item.drug,
                    prescription_id=item.prescription_id,
                    dispense_id=record.id,
                    patient_id=patient_id,
                    batch_no=batch_no,
                    quantity=quantity,
                    operator=operator,
                    witness=data.witness.strip(),
                )
            db.add(
                DispenseItem(
                    dispense_id=record.id,
                    prescription_item_id=item.id,
                    drug_id=item.drug_id,
                    drug_name=item.drug_name,
                    spec=(item.drug.spec if item.drug else ""),
                    batch_no=batch_no,
                    expiry=expiry,
                    quantity=quantity,
                    unit_price=item.unit_price,
                    amount=round(quantity * item.unit_price, 2),
                )
            )

    call = (
        db.query(PharmacyCall)
        .filter(PharmacyCall.encounter_id == encounter.id)
        .first()
    )
    if call:
        call.status = "dispensed"
    if pickup:
        pickup.used_at = datetime.now()
    for header in headers:
        header.status = "dispensed"
        header.updated_at = datetime.now()

    db.commit()
    db.refresh(record)
    return record


def _next_queue_no(db: Session) -> str:
    today = datetime.now().date()
    count = (
        db.query(PharmacyCall)
        .filter(func.date(PharmacyCall.called_at) == today.isoformat())
        .count()
    )
    return f"Q{today:%Y%m%d}{count + 1:03d}"


def call_patient(db: Session, encounter_id: int, window_no: str, operator: str, note: str = "") -> PharmacyCall:
    encounter = get_encounter(db, encounter_id)
    if not encounter:
        raise ValueError("就诊记录不存在")
    payment = get_payment_by_encounter(db, encounter_id)
    if not payment or payment.status not in ("paid", "partially_refunded"):
        raise ValueError("该就诊尚未收费")
    from app.modules.encounter.models import Prescription

    headers = (
        db.query(Prescription)
        .filter(Prescription.encounter_id == encounter_id, Prescription.type != "tcm_herb")
        .all()
    )
    if not headers or any(
        row.status in ("pending_review", "draft", "rejected") for row in headers
    ):
        raise ValueError("存在未通过药师审核的处方，不能叫号")
    if (
        db.query(Dispense)
        .filter(
            Dispense.encounter_id == encounter_id,
            Dispense.status.in_(("dispensed", "partially_returned")),
        )
        .first()
    ):
        raise ValueError("该就诊已发药")
    if not list_prescription_items(db, encounter_id):
        raise ValueError("该就诊没有处方")
    call = (
        db.query(PharmacyCall)
        .filter(PharmacyCall.encounter_id == encounter_id)
        .first()
    )
    if call:
        call.status = "called"
        call.window_no = window_no
        call.called_by = operator
        call.called_at = datetime.now()
        call.note = note
    else:
        call = PharmacyCall(
            encounter_id=encounter_id,
            queue_no=_next_queue_no(db),
            window_no=window_no,
            called_by=operator,
            note=note,
        )
        db.add(call)
    db.commit()
    db.refresh(call)
    return call


def _ensure_code(db: Session, encounter_id: int) -> PharmacyPickupCode:
    row = (
        db.query(PharmacyPickupCode)
        .filter(PharmacyPickupCode.encounter_id == encounter_id)
        .first()
    )
    if row:
        if row.used_at is not None:
            # 退药/退费后重新开方：旧码作废，生成新码
            alphabet = string.ascii_uppercase + string.digits
            for _ in range(20):
                new_code = "P" + "".join(secrets.choice(alphabet) for _ in range(6))
                if not db.query(PharmacyPickupCode).filter(
                    PharmacyPickupCode.code == new_code
                ).first():
                    row.code = new_code
                    row.used_at = None
                    db.commit()
                    db.refresh(row)
                    return row
        return row
    alphabet = string.ascii_uppercase + string.digits
    for _ in range(20):
        code = "P" + "".join(secrets.choice(alphabet) for _ in range(6))
        if not db.query(PharmacyPickupCode).filter(PharmacyPickupCode.code == code).first():
            row = PharmacyPickupCode(encounter_id=encounter_id, code=code)
            db.add(row)
            db.flush()
            return row
    raise ValueError("取药码生成失败")


def verify_pickup(db: Session, code: str) -> dict:
    row = (
        db.query(PharmacyPickupCode)
        .filter(PharmacyPickupCode.code == code.strip().upper())
        .first()
    )
    if not row:
        raise ValueError("取药码不存在")
    if row.used_at is not None:
        raise ValueError("取药码已使用")
    encounter = db.get(Encounter, row.encounter_id)
    patient = (
        db.query(Patient)
        .join(Registration, Registration.patient_id == Patient.id)
        .filter(Registration.id == encounter.registration_id)
        .first()
        if encounter
        else None
    )
    return {
        "encounter_id": row.encounter_id,
        "patient_name": patient.name if patient else "",
        "code": row.code,
        "used": bool(row.used_at),
    }


def worklist(db: Session) -> list[dict]:
    rows = (
        db.query(Payment, Patient, Registration)
        .join(Encounter, Payment.encounter_id == Encounter.id)
        .join(Registration, Encounter.registration_id == Registration.id)
        .join(Patient, Registration.patient_id == Patient.id)
        .filter(Payment.status.in_(("paid", "partially_refunded")))
        .order_by(Payment.created_at)
        .all()
    )
    from app.modules.encounter.models import Prescription

    result = []
    for payment, patient, registration in rows:
        items = list_prescription_items(db, payment.encounter_id)
        if not items:
            continue
        headers = (
            db.query(Prescription)
            .filter(
                Prescription.encounter_id == payment.encounter_id,
                Prescription.type != "tcm_herb",
            )
            .all()
        )
        # 只有全部处方已审方通过才进入待发药队列；待审/驳回不叫号。
        if not headers or any(
            row.status in ("pending_review", "draft", "rejected") for row in headers
        ):
            continue
        dispense = (
            db.query(Dispense)
            .filter(
                Dispense.encounter_id == payment.encounter_id,
                Dispense.status.in_(("dispensed", "partially_returned")),
            )
            .first()
        )
        if dispense:
            continue
        call = (
            db.query(PharmacyCall)
            .filter(PharmacyCall.encounter_id == payment.encounter_id)
            .first()
        )
        result.append(
            {
                "encounter_id": payment.encounter_id,
                "patient_id": patient.id,
                "patient_no": patient.patient_no,
                "patient_name": patient.name,
                "gender": patient.gender,
                "birth_date": patient.birth_date.isoformat() if patient.birth_date else "",
                "allergy_label": patient.allergy_label,
                "pickup_code": _ensure_code(db, payment.encounter_id).code,
                "queue_no": call.queue_no if call else "",
                "call_status": call.status if call else "waiting",
                "window_no": call.window_no if call else "",
                "paid_at": payment.created_at,
                "item_count": len(items),
                "drugs": "、".join(item.drug_name for item in items[:4]),
            }
        )
    db.commit()
    return result




def build_dispense_slip(db: Session, encounter_id: int) -> dict:
    """取药凭证：聚合患者、就诊、费用、处方、发药队列，只读。"""
    from datetime import timedelta

    from app import settings
    from app.modules.billing.models import Payment
    from app.modules.encounter.service import list_encounter_diagnoses
    from app.modules.registration.service import get_registration
    from app.modules.staff.models import Department
    from app.modules.staff.service import get_doctor
    from app.modules.tcm.models import TcmPrescription

    encounter = get_encounter(db, encounter_id)
    if not encounter:
        raise ValueError("就诊记录不存在")
    dispense = (
        db.query(Dispense)
        .filter(Dispense.encounter_id == encounter_id, Dispense.status == "dispensed")
        .first()
    )
    if not dispense:
        raise ValueError("尚未发药，不能打印取药凭证")
    registration = get_registration(db, encounter.registration_id)
    from app.modules.patient.service import get_patient

    patient = get_patient(db, registration.patient_id) if registration else None
    doctor = get_doctor(db, registration.doctor_id) if registration else None
    department = db.get(Department, doctor.department_id) if doctor else None
    payment = (
        db.query(Payment)
        .filter(Payment.encounter_id == encounter_id, Payment.status != "refunded")
        .order_by(Payment.id.desc())
        .first()
    )
    call = (
        db.query(PharmacyCall)
        .filter(PharmacyCall.encounter_id == encounter_id)
        .first()
    )
    pickup = (
        db.query(PharmacyPickupCode)
        .filter(PharmacyPickupCode.encounter_id == encounter_id)
        .first()
    )
    items = list_prescription_items(db, encounter_id)
    name = patient.name if patient else "—"
    masked = (name[0] + "***") if len(name) > 1 else name
    usage_rows = []
    from app.modules.encounter.models import Prescription

    for header in (
        db.query(Prescription)
        .filter(
            Prescription.encounter_id == dispense.encounter_id,
            Prescription.type != "tcm_herb",
            Prescription.status == "dispensed",
        )
        .all()
    ):
        header.status = "returned"
        header.updated_at = datetime.now()

    if dispense.items:
        for line in dispense.items:
            item = next(
                (row for row in items if row.id == line.prescription_item_id), None
            )
            usage = " ".join(
                part
                for part in (
                    item.dosage if item else "",
                    item.frequency if item else "",
                    item.route if item else "",
                    f"{item.days}天" if item and item.days else "",
                )
                if part
            )
            usage_rows.append(
                {
                    "drug_name": line.drug_name,
                    "dosage_form": item.drug.dosage_form if item and item.drug else "",
                    "spec": line.spec,
                    "unit": item.drug.unit if item and item.drug else "",
                    "quantity": line.quantity,
                    "unit_price": line.unit_price,
                    "amount": line.amount,
                    "usage": usage or "—",
                    "batch_no": line.batch_no,
                    "expiry": line.expiry.isoformat() if line.expiry else "",
                }
            )
    else:
        for item in items:
            usage = " ".join(
                part
                for part in (
                    item.dosage,
                    item.frequency,
                    item.route,
                    f"{item.days}天" if item.days else "",
                )
                if part
            )
            usage_rows.append(
                {
                    "drug_name": item.drug_name,
                    "dosage_form": item.drug.dosage_form if item.drug else "",
                    "spec": item.drug.spec if item.drug else "",
                    "unit": item.drug.unit if item.drug else "",
                    "quantity": item.quantity,
                    "unit_price": item.unit_price,
                    "amount": round(item.quantity * item.unit_price, 2),
                    "usage": usage or "—",
                    "batch_no": "",
                    "expiry": "",
                }
            )
    tcm_rows = []
    for rx in (
        db.query(TcmPrescription)
        .filter(TcmPrescription.encounter_id == encounter_id)
        .order_by(TcmPrescription.id)
        .all()
    ):
        tcm_rows.append(
            {
                "prescription_no": rx.prescription_no,
                "formula_name": rx.formula_name,
                "packs": rx.packs,
                "decoction_method": rx.decoction_method,
                "items": [
                    {"name": row.herb_name, "dose_g": row.dose_g, "special": row.special}
                    for row in rx.items
                ],
            }
        )
    diagnoses = list_encounter_diagnoses(db, encounter_id)
    diagnosis = encounter.diagnosis or (
        "、".join(row.diagnosis for row in diagnoses if row.diagnosis) if diagnoses else ""
    )
    waiting_query = db.query(PharmacyCall).filter(PharmacyCall.status == "called")
    if call and call.window_no:
        waiting_query = waiting_query.filter(PharmacyCall.window_no == call.window_no)
    waiting_count = waiting_query.count()
    settled_at = payment.created_at if payment else None
    return {
        "encounter_id": encounter.id,
        "patient": {
            "name": masked,
            "gender": {"male": "男", "female": "女"}.get(
                patient.gender if patient else "", "不详"
            ),
            "age": patient.age if patient else None,
            "patient_no": patient.patient_no if patient and patient.patient_no else str(patient.id) if patient else "",
        },
        "registration_id": registration.id if registration else None,
        "department": department.name if department else "",
        "doctor_name": doctor.name if doctor else "",
        "settled_at": settled_at.isoformat() if settled_at else None,
        "printed_at": datetime.now().isoformat(timespec="seconds"),
        "valid_until": (
            (settled_at + timedelta(days=1)).date().isoformat()
            if settled_at
            else None
        ),
        "pharmacy_name": f"{settings.CLINIC_NAME} 门诊西药房",
        "window_no": call.window_no if call else "",
        "queue_no": call.queue_no if call else (pickup.code if pickup else ""),
        "waiting_count": waiting_count,
        "prescription_count": (1 if items else 0) + len(tcm_rows),
        "diagnosis": diagnosis,
        "items": usage_rows,
        "tcm_prescriptions": tcm_rows,
        "signatures": {
            "doctor": doctor.name if doctor else "",
            "dispenser": dispense.verified_by,
            "checker": dispense.verified_by,
            "receiver": dispense.receiver_name,
        },
        "dispensed_at": (
            dispense.verified_at.isoformat(timespec="seconds")
            if dispense.verified_at
            else None
        ),
        "tips": [
            "取药凭证是执行指引和用药核对清单，不等同于处方。",
            "如需报销，请另行打印正规处方。",
        ],
    }


def deduct_stock(
    db: Session,
    drug,
    quantity: int,
    *,
    ref_type: str = "dispense",
    ref_id: int | None = None,
    operator: str = "",
    note: str = "",
) -> None:
    """按近效期先出扣减库存（不提交事务）；不足抛 ValueError。

    过期批次和未完成召回批次自然锁定（不在可选范围）。门诊发药与住院摆药共用。
    """
    from app.modules.gsp.models import GspRecall

    recalls = (
        db.query(GspRecall)
        .filter(
            GspRecall.drug_name == drug.name,
            GspRecall.status == "initiated",
        )
        .all()
    )

    def _recalled(batch_no: str) -> bool:
        return any(
            (not row.batch_no) or row.batch_no == batch_no for row in recalls
        )

    stock_rows = (
        db.query(DrugStock)
        .filter(
            DrugStock.drug_id == drug.id,
            DrugStock.quantity > 0,
            DrugStock.expiry >= date.today(),
        )
        .order_by(DrugStock.expiry.asc())
        .all()
    )
    remaining = quantity
    blocked = False
    allocations: list[tuple[str, date, int]] = []
    for stock in stock_rows:
        if remaining <= 0:
            break
        if _recalled(stock.batch_no):
            blocked = True
            continue
        take = min(stock.quantity, remaining)
        if take <= 0:
            continue
        # 原子条件扣减：并发下 quantity 不会被扣成负数
        affected = (
            db.query(DrugStock)
            .filter(DrugStock.id == stock.id, DrugStock.quantity >= take)
            .update(
                {DrugStock.quantity: DrugStock.quantity - take},
                synchronize_session=False,
            )
        )
        if affected != 1:
            raise ValueError(f"库存不足：{drug.name}")
        db.expire(stock)
        record_drug(
            db,
            drug,
            batch_no=stock.batch_no,
            expiry=stock.expiry,
            warehouse="药房",
            direction="out",
            quantity=take,
            unit_price=drug.base_price,
            ref_type=ref_type,
            ref_id=ref_id,
            operator=operator,
            note=note,
        )
        allocations.append((stock.batch_no, stock.expiry, take))
        remaining -= take
    if remaining > 0:
        if blocked:
            raise ValueError(
                f"药品「{drug.name}」存在未完成召回批次，禁止发药/出库"
            )
        raise ValueError(f"库存不足：{drug.name}")
    return allocations


def restore_stock(
    db: Session,
    drug,
    quantity: int,
    *,
    ref_type: str = "dispense_return",
    ref_id: int | None = None,
    operator: str = "",
    note: str = "",
    batch_no: str | None = None,
) -> None:
    """退药回补库存（不提交事务）：优先回补实际发药批次。"""
    query = db.query(DrugStock).filter(DrugStock.drug_id == drug.id)
    if batch_no:
        query = query.filter(DrugStock.batch_no == batch_no)
    batch = query.order_by(DrugStock.id).first()
    if not batch:
        raise ValueError("没有可回退的药品批次")
    batch.quantity += quantity
    db.flush()
    record_drug(
        db,
        drug,
        batch_no=batch.batch_no,
        expiry=batch.expiry,
        warehouse="药房",
        direction="in",
        quantity=quantity,
        unit_price=drug.base_price,
        ref_type=ref_type,
        ref_id=ref_id,
        operator=operator,
        note=note,
    )


def get_dispense(db: Session, dispense_id: int) -> Dispense | None:
    """按 ID 查询发药记录；不存在时返回 None。"""
    return db.get(Dispense, dispense_id)


def get_dispense_by_encounter(db: Session, encounter_id: int) -> Dispense | None:
    """按就诊查发药记录；优先当前有效记录，其次最近一次。"""
    rows = (
        db.query(Dispense)
        .filter(Dispense.encounter_id == encounter_id)
        .order_by(Dispense.id.desc())
        .all()
    )
    for row in rows:
        if row.status in ("dispensed", "partially_returned"):
            return row
    return rows[0] if rows else None


def get_active_dispense_by_encounter(
    db: Session, encounter_id: int
) -> Dispense | None:
    """按就诊查未退回的发药记录（退费拦截用）。"""
    return (
        db.query(Dispense)
        .filter(
            Dispense.encounter_id == encounter_id,
            Dispense.status.in_(("dispensed", "partially_returned")),
        )
        .first()
    )


def return_dispense(db: Session, dispense_id: int, operator: str = "") -> Dispense:
    """门诊退药：库存回补，状态置 returned（原子状态机防并发重复退）。"""
    dispense = get_dispense(db, dispense_id)
    if not dispense:
        raise ValueError("发药记录不存在")
    if dispense.status != "dispensed":
        raise ValueError("该发药记录已退回")

    affected = (
        db.query(Dispense)
        .filter(Dispense.id == dispense_id, Dispense.status == "dispensed")
        .update(
            {
                Dispense.status: "returned",
                Dispense.returned_at: datetime.now(),
            },
            synchronize_session=False,
        )
    )
    if affected != 1:
        raise ValueError("该发药记录已退回")

    from app.modules.encounter.models import Prescription

    for header in (
        db.query(Prescription)
        .filter(
            Prescription.encounter_id == dispense.encounter_id,
            Prescription.type != "tcm_herb",
            Prescription.status == "dispensed",
        )
        .all()
    ):
        header.status = "returned"
        header.updated_at = datetime.now()

    if dispense.items:
        for line in dispense.items:
            remain = line.quantity - (line.returned_quantity or 0)
            if remain <= 0:
                continue
            restore_stock(
                db,
                get_drug(db, line.drug_id) if line.drug_id else None,
                remain,
                ref_type="dispense_return",
                ref_id=dispense.id,
                operator=operator,
                batch_no=line.batch_no,
            )
            if getattr(get_drug(db, line.drug_id), "controlled_level", ""):
                from app.modules.narcotic.service import record_return

                record_return(
                    db,
                    line=line,
                    dispense_id=dispense.id,
                    quantity=remain,
                    operator=operator,
                )
            line.returned_quantity += remain
    else:
        # 旧数据没有明细，按处方回补
        for item in list_dispensable_prescription_items(db, dispense.encounter_id):
            restore_stock(
                db,
                item.drug,
                item.quantity,
                ref_type="dispense_return",
                ref_id=dispense.id,
                operator=operator,
            )

    db.commit()
    db.refresh(dispense)
    return dispense


def return_dispense_items(
    db: Session,
    dispense_id: int,
    items: list,
    *,
    operator: str = "",
    reason: str = "",
) -> Dispense:
    """按发药明细部分退药；全部退完才置 returned。"""
    dispense = get_dispense(db, dispense_id)
    if not dispense:
        raise ValueError("发药记录不存在")
    if dispense.status not in ("dispensed", "partially_returned"):
        raise ValueError("该发药记录已退回")

    lines = {line.id: line for line in dispense.items}
    requested: dict[int, int] = {}
    for item in items:
        line_id = item.line_id if hasattr(item, "line_id") else item["line_id"]
        quantity = item.quantity if hasattr(item, "quantity") else item["quantity"]
        requested[line_id] = requested.get(line_id, 0) + quantity

    for line_id, quantity in requested.items():
        line = lines.get(line_id)
        if not line:
            raise ValueError("发药明细不存在或不属于该发药记录")
        remain = line.quantity - (line.returned_quantity or 0)
        if quantity > remain:
            raise ValueError(f"退药数量超过可退数量：{line.drug_name}")

    for line_id, quantity in requested.items():
        line = lines[line_id]
        drug = get_drug(db, line.drug_id) if line.drug_id else None
        restore_stock(
            db,
            drug,
            quantity,
            ref_type="dispense_return",
            ref_id=dispense.id,
            operator=operator,
            batch_no=line.batch_no,
        )
        if drug and getattr(drug, "controlled_level", ""):
            from app.modules.narcotic.service import record_return

            record_return(
                db,
                line=line,
                dispense_id=dispense.id,
                quantity=quantity,
                operator=operator,
            )
        line.returned_quantity = (line.returned_quantity or 0) + quantity

    all_returned = all(
        (line.returned_quantity or 0) >= line.quantity for line in dispense.items
    )
    dispense.status = "returned" if all_returned else "partially_returned"
    if all_returned:
        dispense.returned_at = datetime.now()
        from app.modules.encounter.models import Prescription

        for header in (
            db.query(Prescription)
            .filter(
                Prescription.encounter_id == dispense.encounter_id,
                Prescription.type != "tcm_herb",
                Prescription.status == "dispensed",
            )
            .all()
        ):
            header.status = "returned"
            header.updated_at = datetime.now()
    if reason:
        dispense.note = (dispense.note or "") + f"；部分退药：{reason}"
    db.commit()
    db.refresh(dispense)
    return dispense
