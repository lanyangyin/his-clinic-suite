"""中药处方与煎药室：饮片处方→审核→发药→浸泡→煎煮→包装→发放。"""
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.modules.charges.service import add_charge
from app.modules.encounter.models import Encounter
from app.modules.encounter.service import get_encounter
from app.modules.patient.models import Patient
from app.modules.registration.models import Registration

from .models import DecoctionBag, DecoctionOrder, TcmHerb, TcmPrescription, TcmPrescriptionItem
from .schemas import (
    DecoctRequest,
    HerbCreate,
    IssueRequest,
    PackageRequest,
    PrescriptionCreate,
    SoakRequest,
)

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
    total = 0.0
    for item, herb in herbs:
        total += herb.price_per_g * item.dose_g * data.packs
        db.add(
            TcmPrescriptionItem(
                prescription_id=prescription.id,
                herb_id=herb.id,
                herb_name=herb.name,
                dose_g=item.dose_g,
                special=item.special,
                note=item.note,
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
    prescription.status = "dispensed"
    prescription.dispense_by = operator
    prescription.dispensed_at = datetime.now()
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
