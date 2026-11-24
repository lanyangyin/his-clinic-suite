"""中药处方与煎药室：饮片处方→审核→发药→浸泡→煎煮→包装→发放。"""
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.modules.charges.service import add_charge
from app.modules.encounter.models import Encounter, Prescription, PrescriptionLine
from app.modules.charges.models import EncounterCharge
from app.modules.encounter.service import get_encounter
from app.modules.patient.models import Patient
from app.modules.registration.models import Registration

from .models import (
    DecoctionBag,
    DecoctionOrder,
    TcmHerb,
    TcmPrescription,
    TcmPrescriptionItem,
    TcmStockAdjustment,
    TcmStockBatch,
)
from .schemas import (
    DecoctRequest,
    HerbCreate,
    IssueRequest,
    PackageRequest,
    PrescriptionCreate,
    SoakRequest,
    StockAdjustRequest,
    StockBatchCreate,
)

# 十八反、十九畏的核心药对；名称做去炮制前缀后的包含匹配
INCOMPATIBLE_PAIRS = (
    ("甘草", "甘遂"), ("甘草", "大戟"), ("甘草", "海藻"), ("甘草", "芫花"),
    ("乌头", "贝母"), ("乌头", "瓜蒌"), ("乌头", "半夏"), ("乌头", "白蔹"), ("乌头", "白及"),
    ("藜芦", "人参"), ("藜芦", "沙参"), ("藜芦", "丹参"), ("藜芦", "玄参"),
    ("藜芦", "细辛"), ("藜芦", "芍药"),
    ("硫黄", "朴硝"), ("水银", "砒霜"), ("狼毒", "密陀僧"), ("巴豆", "牵牛"),
    ("丁香", "郁金"), ("川乌", "犀角"), ("草乌", "犀角"), ("牙硝", "三棱"),
    ("官桂", "石脂"), ("人参", "五灵脂"),
)


def _check_incompatibility(herbs: list[TcmHerb]) -> None:
    names = [(herb.name or "").strip() for herb in herbs]
    for left, right in INCOMPATIBLE_PAIRS:
        if any(left in name for name in names) and any(right in name for name in names):
            raise ValueError(f"存在配伍禁忌：{left} 与 {right}，请核对后再开方")


SPECIAL_LABELS = {
    "none": "",
    "first": "先煎",
    "last": "后下",
    "wrap": "包煎",
    "separate": "另煎",
    "melt": "烊化",
    "infuse": "冲服",
}


def create_herb(db: Session, data: HerbCreate) -> TcmHerb:
    if db.query(TcmHerb).filter(TcmHerb.code == data.code).first():
        raise ValueError("饮片编码已存在")
    row = TcmHerb(**data.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def list_herbs(db: Session, active_only: bool = True) -> list[TcmHerb]:
    query = db.query(TcmHerb)
    if active_only:
        query = query.filter(TcmHerb.active.is_(True))
    return query.order_by(TcmHerb.name).all()


def get_herb(db: Session, herb_id: int) -> TcmHerb | None:
    return db.get(TcmHerb, herb_id)


def add_stock_batch(db: Session, herb_id: int, data: StockBatchCreate) -> TcmStockBatch:
    herb = get_herb(db, herb_id)
    if not herb:
        raise ValueError("饮片不存在")
    if db.query(TcmStockBatch).filter(
        TcmStockBatch.herb_id == herb_id, TcmStockBatch.batch_no == data.batch_no
    ).first():
        raise ValueError("该饮片批号已存在")
    row = TcmStockBatch(herb_id=herb_id, **data.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def list_stock_batches(db: Session, herb_id: int) -> list[TcmStockBatch]:
    return (
        db.query(TcmStockBatch)
        .filter(TcmStockBatch.herb_id == herb_id)
        .order_by(TcmStockBatch.expiry.asc().nulls_last(), TcmStockBatch.id.asc())
        .all()
    )


def list_all_stock_batches(db: Session, herb_id: int | None = None) -> list[dict]:
    query = (
        db.query(TcmStockBatch, TcmHerb)
        .join(TcmHerb, TcmStockBatch.herb_id == TcmHerb.id)
    )
    if herb_id:
        query = query.filter(TcmStockBatch.herb_id == herb_id)
    rows = query.order_by(TcmStockBatch.expiry.asc().nulls_last(), TcmStockBatch.id.asc()).all()
    return [
        {
            "id": batch.id,
            "herb_id": herb.id,
            "herb_code": herb.code,
            "herb_name": herb.name,
            "batch_no": batch.batch_no,
            "quantity_g": batch.quantity_g,
            "expiry": batch.expiry,
            "expired": bool(batch.expiry and batch.expiry < datetime.now()),
        }
        for batch, herb in rows
    ]


def adjust_stock_batch(
    db: Session, batch_id: int, data: StockAdjustRequest, operator: str = ""
) -> dict:
    batch = db.get(TcmStockBatch, batch_id)
    if not batch:
        raise ValueError("饮片批次不存在")
    new_qty = round(batch.quantity_g + data.delta_g, 2)
    if new_qty < 0:
        raise ValueError(f"调整后库存不能为负：现有 {batch.quantity_g:g}g")
    batch.quantity_g = new_qty
    row = TcmStockAdjustment(
        batch_id=batch.id,
        delta_g=data.delta_g,
        reason=data.reason.strip(),
        operator=operator,
        status="approved",
        approved_by=operator,
        approved_at=datetime.now(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {
        "id": row.id,
        "batch_id": batch.id,
        "delta_g": row.delta_g,
        "reason": row.reason,
        "operator": row.operator,
        "created_at": row.created_at,
        "quantity_g": batch.quantity_g,
    }


def request_stock_adjustment(
    db: Session, batch_id: int, data: StockAdjustRequest, operator: str = ""
) -> TcmStockAdjustment:
    batch = db.get(TcmStockBatch, batch_id)
    if not batch:
        raise ValueError("饮片批次不存在")
    if not data.reason.strip():
        raise ValueError("请填写调整原因")
    row = TcmStockAdjustment(
        batch_id=batch.id,
        delta_g=data.delta_g,
        reason=data.reason.strip(),
        operator=operator,
        status="pending",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def approve_stock_adjustment(
    db: Session, adjustment_id: int, approve: bool, reviewer: str, note: str = ""
) -> TcmStockAdjustment:
    row = db.get(TcmStockAdjustment, adjustment_id)
    if not row:
        raise ValueError("调整申请不存在")
    if row.status != "pending":
        raise ValueError("该调整申请已处理")
    if not approve:
        row.status = "rejected"
        row.approved_by = reviewer
        row.approved_at = datetime.now()
        if note:
            row.reason = f"{row.reason}（驳回：{note}）"
        db.commit()
        db.refresh(row)
        return row
    batch = db.get(TcmStockBatch, row.batch_id)
    if not batch:
        raise ValueError("饮片批次不存在")
    new_qty = round(batch.quantity_g + row.delta_g, 2)
    if new_qty < 0:
        raise ValueError(f"调整后库存不能为负：现有 {batch.quantity_g:g}g")
    batch.quantity_g = new_qty
    row.status = "approved"
    row.approved_by = reviewer
    row.approved_at = datetime.now()
    db.commit()
    db.refresh(row)
    return row


def _deduct_batches(db: Session, herb: TcmHerb, needed: float) -> bool:
    batches = (
        db.query(TcmStockBatch)
        .filter(
            TcmStockBatch.herb_id == herb.id,
            TcmStockBatch.quantity_g > 0,
            (TcmStockBatch.expiry.is_(None)) | (TcmStockBatch.expiry >= datetime.now()),
        )
        .order_by(TcmStockBatch.expiry.asc().nulls_last(), TcmStockBatch.id.asc())
        .all()
    )
    if not batches:
        has_any = (
            db.query(TcmStockBatch)
            .filter(TcmStockBatch.herb_id == herb.id, TcmStockBatch.quantity_g > 0)
            .first()
        )
        if has_any:
            raise ValueError(f"饮片 {herb.name} 无有效批次（已过期）")
        return False
    available = round(sum(batch.quantity_g for batch in batches), 2)
    if available < needed:
        raise ValueError(f"饮片库存不足：{herb.name} 需要 {needed:g}g，现有 {available:g}g")
    remaining = needed
    for batch in batches:
        take = min(batch.quantity_g, remaining)
        batch.quantity_g = round(batch.quantity_g - take, 2)
        remaining = round(remaining - take, 2)
        if remaining <= 0:
            break
    return True


def _next_prescription_no(db: Session) -> str:
    last = db.query(TcmPrescription.id).order_by(TcmPrescription.id.desc()).first()
    return f"TCM{datetime.now():%Y%m%d}{(last[0] if last else 0) + 1:04d}"


def create_prescription(
    db: Session, encounter_id: int, data: PrescriptionCreate, doctor: str = ""
) -> TcmPrescription:
    encounter = get_encounter(db, encounter_id)
    if not encounter:
        raise ValueError("就诊记录不存在")
    if encounter.status == "closed":
        raise ValueError("就诊已关闭，不能开中药处方")
    if not data.items:
        raise ValueError("中药处方至少需要一味饮片")

    herbs = []
    for item in data.items:
        herb = get_herb(db, item.herb_id)
        if not herb or not herb.active:
            raise ValueError(f"饮片不存在：{item.herb_id}")
        herbs.append((item, herb))

    _check_incompatibility([herb for _item, herb in herbs])
    for item, herb in herbs:
        if herb.toxicity == "toxic" and herb.max_dose_g > 0 and item.dose_g > herb.max_dose_g:
            raise ValueError(
                f"毒性饮片 {herb.name} 单味剂量 {item.dose_g:g}g 超过上限 {herb.max_dose_g:g}g"
            )

    prescription = TcmPrescription(
        prescription_no=_next_prescription_no(db),
        encounter_id=encounter_id,
        doctor=doctor,
        formula_name=data.formula_name,
        usage=data.usage,
        packs=data.packs,
        decoct_service=data.decoct_service,
        decoction_method=data.decoction_method,
        note=data.note,
    )
    db.add(prescription)
    db.flush()
    header = Prescription(
        encounter_id=encounter_id,
        prescription_no=f"TCM{datetime.now():%Y%m%d}{prescription.id:06d}",
        type="tcm_herb",
        status="pending_review",
        prescribed_by=doctor,
    )
    db.add(header)
    db.flush()
    prescription.prescription_id = header.id
    total = 0.0
    for item, herb in herbs:
        total += herb.price_per_g * item.dose_g * data.packs
        tcm_item = TcmPrescriptionItem(
            prescription_id=prescription.id,
            herb_id=herb.id,
            herb_name=herb.name,
            dose_g=item.dose_g,
            special=item.special,
            note=item.note,
        )
        db.add(tcm_item)
        db.flush()
        db.add(
            PrescriptionLine(
                prescription_id=header.id,
                kind="herb",
                herb_id=herb.id,
                source_item_id=tcm_item.id,
                name=herb.name,
                spec=herb.spec,
                quantity=item.dose_g,
                unit=herb.unit,
                days=data.packs,
                unit_price=herb.price_per_g,
                amount=round(herb.price_per_g * item.dose_g * data.packs, 2),
            )
        )
    prescription.total_amount = round(total, 2)
    if total > 0:
        add_charge(
            db,
            encounter_id=encounter_id,
            source_type="tcm_prescription",
            source_id=prescription.id,
            charge_type="drug",
            item_name=f"中药：{data.formula_name or prescription.prescription_no}",
            quantity=data.packs,
            unit_price=round(total / data.packs, 2) if data.packs else total,
            insurance_ratio=0.7,
        )
    db.commit()
    db.refresh(prescription)
    return prescription


def list_prescriptions(
    db: Session,
    status: str | None = None,
    encounter_id: int | None = None,
) -> list[dict]:
    query = (
        db.query(TcmPrescription, Patient)
        .join(Encounter, TcmPrescription.encounter_id == Encounter.id)
        .join(Registration, Encounter.registration_id == Registration.id)
        .join(Patient, Registration.patient_id == Patient.id)
    )
    if status:
        statuses = [item.strip() for item in status.split(",") if item.strip()]
        if statuses:
            query = query.filter(TcmPrescription.status.in_(statuses))
    if encounter_id:
        query = query.filter(TcmPrescription.encounter_id == encounter_id)
    rows = query.order_by(TcmPrescription.id.desc()).all()
    result = []
    for prescription, patient in rows:
        encounter = get_encounter(db, prescription.encounter_id)
        result.append(
            {
                "id": prescription.id,
                "prescription_no": prescription.prescription_no,
                "encounter_id": prescription.encounter_id,
                "patient_id": patient.id,
                "patient_name": patient.name,
                "diagnosis": encounter.diagnosis if encounter else "",
                "doctor": prescription.doctor,
                "formula_name": prescription.formula_name,
                "usage": prescription.usage,
                "packs": prescription.packs,
                "decoct_service": prescription.decoct_service,
                "decoction_method": prescription.decoction_method,
                "status": prescription.status,
                "total_amount": prescription.total_amount,
                "review_by": prescription.review_by,
                "dispense_by": prescription.dispense_by,
                "created_at": prescription.created_at,
                "items": [
                    {
                        "herb_name": item.herb_name,
                        "dose_g": item.dose_g,
                        "special": item.special,
                    }
                    for item in prescription.items
                ],
            }
        )
    return result


def get_prescription(db: Session, prescription_id: int) -> TcmPrescription | None:
    return db.get(TcmPrescription, prescription_id)


def _recalc_total(db: Session, prescription: TcmPrescription) -> None:
    items = (
        db.query(TcmPrescriptionItem)
        .filter(TcmPrescriptionItem.prescription_id == prescription.id)
        .all()
    )
    total = 0.0
    for item in items:
        herb = get_herb(db, item.herb_id)
        if herb:
            total += herb.price_per_g * item.dose_g * prescription.packs
    prescription.total_amount = round(total, 2)
    charge = (
        db.query(EncounterCharge)
        .filter(
            EncounterCharge.source_type == "tcm_prescription",
            EncounterCharge.source_id == prescription.id,
        )
        .first()
    )
    if charge and charge.status == "paid":
        raise ValueError("该中药处方已收费，不能修改剂量；请先退费")
    if charge:
        charge.quantity = prescription.packs
        charge.unit_price = round(total / prescription.packs, 2) if prescription.packs else total
        charge.amount = prescription.total_amount


def update_prescription_item(
    db: Session, prescription_id: int, item_id: int, data, operator: str = ""
) -> TcmPrescription:
    prescription = get_prescription(db, prescription_id)
    if not prescription:
        raise ValueError("中药处方不存在")
    if prescription.status != "pending":
        raise ValueError("只有待审核中药处方可以修改饮片")
    item = db.get(TcmPrescriptionItem, item_id)
    if not item or item.prescription_id != prescription_id:
        raise ValueError("饮片明细不存在")
    item.dose_g = data.dose_g
    item.special = data.special
    item.note = data.note
    line = (
        db.query(PrescriptionLine)
        .filter(
            PrescriptionLine.kind == "herb",
            PrescriptionLine.source_item_id == item.id,
        )
        .first()
    )
    if line:
        herb = get_herb(db, item.herb_id)
        line.quantity = item.dose_g
        line.amount = round((herb.price_per_g if herb else 0) * item.dose_g * prescription.packs, 2)
    _recalc_total(db, prescription)
    db.commit()
    db.refresh(prescription)
    return prescription


def delete_prescription_item(db: Session, prescription_id: int, item_id: int) -> TcmPrescription:
    prescription = get_prescription(db, prescription_id)
    if not prescription:
        raise ValueError("中药处方不存在")
    if prescription.status != "pending":
        raise ValueError("只有待审核中药处方可以删除饮片")
    item = db.get(TcmPrescriptionItem, item_id)
    if not item or item.prescription_id != prescription_id:
        raise ValueError("饮片明细不存在")
    item_count = (
        db.query(TcmPrescriptionItem)
        .filter(TcmPrescriptionItem.prescription_id == prescription_id)
        .count()
    )
    if item_count <= 1:
        raise ValueError("中药处方至少保留一味饮片")
    line = (
        db.query(PrescriptionLine)
        .filter(
            PrescriptionLine.kind == "herb",
            PrescriptionLine.source_item_id == item.id,
        )
        .first()
    )
    if line:
        db.delete(line)
    db.delete(item)
    db.flush()
    _recalc_total(db, prescription)
    db.commit()
    db.refresh(prescription)
    return prescription


def review_prescription(
    db: Session, prescription_id: int, operator: str = ""
) -> TcmPrescription:
    prescription = get_prescription(db, prescription_id)
    if not prescription:
        raise ValueError("中药处方不存在")
    if prescription.status != "pending":
        raise ValueError("该处方当前状态不可审核")
    prescription.status = "reviewed"
    prescription.review_by = operator
    prescription.reviewed_at = datetime.now()
    if prescription.prescription_id:
        header = db.get(Prescription, prescription.prescription_id)
        if header:
            header.status = "approved"
            header.reviewed_by = operator
            header.reviewed_at = datetime.now()
            header.updated_at = datetime.now()
    db.commit()
    db.refresh(prescription)
    return prescription


def dispense_prescription(
    db: Session, prescription_id: int, operator: str = ""
) -> TcmPrescription:
    prescription = get_prescription(db, prescription_id)
    if not prescription:
        raise ValueError("中药处方不存在")
    if prescription.status != "reviewed":
        raise ValueError("处方未审核，不能发药")
    # 饮片库存校验：未启用库存（None）的饮片不拦截
    for item in prescription.items:
        herb = get_herb(db, item.herb_id)
        if herb:
            needed = round(item.dose_g * prescription.packs, 2)
            if not _deduct_batches(db, herb, needed):
                if herb.stock_g is not None and herb.stock_g < needed:
                    raise ValueError(f"饮片库存不足：{herb.name} 需要 {needed:g}g，现有 {herb.stock_g:g}g")
    prescription.status = "dispensed"
    prescription.dispense_by = operator
    prescription.dispensed_at = datetime.now()
    if prescription.prescription_id:
        header = db.get(Prescription, prescription.prescription_id)
        if header:
            header.status = "dispensing" if prescription.decoct_service == "decoct" else "dispensed"
            header.updated_at = datetime.now()
    for item in prescription.items:
        herb = get_herb(db, item.herb_id)
        if herb and herb.stock_g is not None and not db.query(TcmStockBatch).filter(TcmStockBatch.herb_id == herb.id).first():
            herb.stock_g = round(max(0.0, herb.stock_g - item.dose_g * prescription.packs), 2)
    if prescription.decoct_service == "decoct":
        encounter = get_encounter(db, prescription.encounter_id)
        registration = db.get(Registration, encounter.registration_id) if encounter else None
        patient = db.get(Patient, registration.patient_id) if registration else None
        order = DecoctionOrder(
            order_no=f"DEC{datetime.now():%Y%m%d}{prescription.id:05d}",
            prescription_id=prescription.id,
            encounter_id=prescription.encounter_id,
            patient_name=patient.name if patient else "",
            status="received",
        )
        db.add(order)
        prescription.status = "decocting"
    else:
        prescription.status = "completed"
    db.commit()
    db.refresh(prescription)
    return prescription


def list_decoctions(db: Session, status: str | None = None) -> list[dict]:
    query = (
        db.query(DecoctionOrder, Patient)
        .join(Encounter, DecoctionOrder.encounter_id == Encounter.id)
        .join(Registration, Encounter.registration_id == Registration.id)
        .join(Patient, Registration.patient_id == Patient.id)
    )
    if status:
        statuses = [item.strip() for item in status.split(",") if item.strip()]
        if statuses:
            query = query.filter(DecoctionOrder.status.in_(statuses))
    rows = query.order_by(DecoctionOrder.id.desc()).all()
    result = []
    for order, patient in rows:
        prescription = get_prescription(db, order.prescription_id)
        result.append(
            {
                "id": order.id,
                "order_no": order.order_no,
                "prescription_id": order.prescription_id,
                "prescription_no": prescription.prescription_no if prescription else "",
                "encounter_id": order.encounter_id,
                "patient_name": patient.name,
                "formula_name": prescription.formula_name if prescription else "",
                "packs": prescription.packs if prescription else 0,
                "status": order.status,
                "soak_minutes": order.soak_minutes,
                "decoct_minutes": order.decoct_minutes,
                "machine_no": order.machine_no,
                "bags": order.bags,
                "received_at": order.received_at,
                "expires_at": order.expires_at,
                "pickup_method": order.pickup_method,
                "receiver": order.receiver,
            }
        )
    return result


def get_decoction(db: Session, order_id: int) -> DecoctionOrder | None:
    return db.get(DecoctionOrder, order_id)


def soak(db: Session, order_id: int, data: SoakRequest, operator: str = "") -> DecoctionOrder:
    order = get_decoction(db, order_id)
    if not order:
        raise ValueError("煎药单不存在")
    if order.status != "received":
        raise ValueError("该煎药单当前状态不可浸泡")
    order.status = "soaking"
    order.soak_minutes = data.soak_minutes
    order.operator = operator
    order.soaked_at = datetime.now()
    order.note = data.note or order.note
    db.commit()
    db.refresh(order)
    return order


def decoct(db: Session, order_id: int, data: DecoctRequest, operator: str = "") -> DecoctionOrder:
    order = get_decoction(db, order_id)
    if not order:
        raise ValueError("煎药单不存在")
    if order.status != "soaking":
        raise ValueError("该煎药单未浸泡，不能煎煮")
    order.status = "decocting"
    order.machine_no = data.machine_no
    order.decoct_minutes = data.decoct_minutes
    order.operator = operator
    order.decocted_at = datetime.now()
    order.note = data.note or order.note
    db.commit()
    db.refresh(order)
    return order


def package(db: Session, order_id: int, data: PackageRequest, operator: str = "") -> DecoctionOrder:
    order = get_decoction(db, order_id)
    if not order:
        raise ValueError("煎药单不存在")
    if order.status != "decocting":
        raise ValueError("该煎药单未煎煮，不能包装")
    order.status = "completed"
    order.bags = data.bags
    order.bag_volume_ml = data.bag_volume_ml
    order.operator = operator
    order.packaged_at = datetime.now()
    order.completed_at = datetime.now()
    order.expires_at = datetime.now() + timedelta(days=data.expires_days)
    order.note = data.note or order.note
    prescription = get_prescription(db, order.prescription_id)
    for index in range(1, data.bags + 1):
        db.add(
            DecoctionBag(
                order_id=order.id,
                bag_no=f"{order.order_no}-{index:03d}",
                expiry=order.expires_at,
                label=(
                    f"患者：{order.patient_name or '—'}　"
                    f"处方：{prescription.prescription_no}　"
                    f"第 {index}/{data.bags} 袋　有效期："
                    f"{order.expires_at.strftime('%Y-%m-%d %H:%M')}"
                ),
            )
        )
    prescription.status = "completed"
    # 代煎处方头也必须结束“调配中”，否则处方中心/打印长期显示未完成
    if prescription.prescription_id:
        header = db.get(Prescription, prescription.prescription_id)
        if header:
            header.status = "dispensed"
            header.updated_at = datetime.now()
    db.commit()
    db.refresh(order)
    return order


def issue(db: Session, order_id: int, data: IssueRequest, operator: str = "") -> DecoctionOrder:
    order = get_decoction(db, order_id)
    if not order:
        raise ValueError("煎药单不存在")
    if order.status != "completed":
        raise ValueError("该煎药单未完成，不能发放")
    order.status = "issued"
    order.pickup_method = data.pickup_method
    order.receiver = data.receiver
    order.issued_at = datetime.now()
    order.operator = operator
    order.note = data.note or order.note
    db.commit()
    db.refresh(order)
    return order
