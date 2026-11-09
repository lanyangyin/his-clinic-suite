"""器械灭菌（CSSD）：灭菌批次、监测放行、包码发放/使用/召回。"""
from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from .models import InstrumentPackage, InstrumentSet, PackageUsage, SterilizationBatch


def _next_batch_no(db: Session) -> str:
    last = db.query(SterilizationBatch.id).order_by(SterilizationBatch.id.desc()).first()
    return f"CSSD{datetime.now():%Y%m%d}{(last[0] if last else 0) + 1:04d}"


def create_set(db: Session, data) -> InstrumentSet:
    if db.query(InstrumentSet).filter(InstrumentSet.code == data.code).first():
        raise ValueError("器械包编码已存在")
    row = InstrumentSet(**data.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def list_sets(db: Session) -> list[InstrumentSet]:
    return db.query(InstrumentSet).order_by(InstrumentSet.id.desc()).all()


def create_batch(db: Session, data) -> SterilizationBatch:
    batch_no = (data.batch_no or "").strip() or _next_batch_no(db)
    if db.query(SterilizationBatch).filter(SterilizationBatch.batch_no == batch_no).first():
        raise ValueError("灭菌批次号已存在")
    payload = data.model_dump(exclude={"batch_no"})
    row = SterilizationBatch(batch_no=batch_no, **payload)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def list_batches(db: Session, release_status: str | None = None) -> list[SterilizationBatch]:
    query = db.query(SterilizationBatch)
    if release_status:
        query = query.filter(SterilizationBatch.release_status == release_status)
    return query.order_by(SterilizationBatch.id.desc()).all()


def get_batch(db: Session, batch_id: int) -> SterilizationBatch | None:
    return db.get(SterilizationBatch, batch_id)


def release_batch(db: Session, batch_id: int, released_by: str = "") -> SterilizationBatch:
    batch = get_batch(db, batch_id)
    if not batch:
        raise ValueError("灭菌批次不存在")
    if batch.release_status != "pending":
        raise ValueError("该批次已放行或已判定不合格")
    if batch.chemical_indicator != "pass" or batch.biological_indicator != "pass":
        raise ValueError("化学/生物监测未全部合格，不能放行")
    batch.release_status = "released"
    batch.released_by = released_by
    batch.released_at = datetime.now()
    batch.ended_at = batch.ended_at or datetime.now()
    db.commit()
    db.refresh(batch)
    return batch


def reject_batch(db: Session, batch_id: int, reason: str = "", operator: str = "") -> SterilizationBatch:
    batch = get_batch(db, batch_id)
    if not batch:
        raise ValueError("灭菌批次不存在")
    batch.release_status = "rejected"
    batch.note = (batch.note + "；" if batch.note else "") + f"不合格：{reason or '未填写'}（{operator}）"
    for package in batch.packages:
        package.status = "recalled"
        package.note = (package.note + "；" if package.note else "") + f"批次不合格召回：{reason}"
    db.commit()
    db.refresh(batch)
    return batch


def create_package(db: Session, data) -> InstrumentPackage:
    if db.query(InstrumentPackage).filter(InstrumentPackage.package_code == data.package_code).first():
        raise ValueError("包码已存在")
    instrument_set = db.get(InstrumentSet, data.set_id)
    batch = db.get(SterilizationBatch, data.batch_id)
    if not instrument_set:
        raise ValueError("器械包不存在")
    if not batch:
        raise ValueError("灭菌批次不存在")
    row = InstrumentPackage(
        package_code=data.package_code,
        set_id=data.set_id,
        batch_id=data.batch_id,
        expiry=data.expiry,
        location=data.location,
        note=data.note,
        sterilized_at=batch.ended_at or datetime.now(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def list_packages(
    db: Session,
    status: str | None = None,
    set_id: int | None = None,
    batch_id: int | None = None,
) -> list[InstrumentPackage]:
    query = db.query(InstrumentPackage)
    if status:
        query = query.filter(InstrumentPackage.status == status)
    if set_id:
        query = query.filter(InstrumentPackage.set_id == set_id)
    if batch_id:
        query = query.filter(InstrumentPackage.batch_id == batch_id)
    return query.order_by(InstrumentPackage.id.desc()).all()


def get_package(db: Session, package_id: int) -> InstrumentPackage | None:
    return db.get(InstrumentPackage, package_id)


def issue_package(db: Session, package_id: int, data, operator: str = "") -> InstrumentPackage:
    package = get_package(db, package_id)
    if not package:
        raise ValueError("器械包不存在")
    if package.batch.release_status != "released":
        raise ValueError("灭菌批次未放行，不能发放")
    if package.status != "sterilized":
        raise ValueError("该包当前状态不可发放")
    if package.expiry < date.today():
        raise ValueError("该包已过期，不能发放")
    package.status = "issued"
    package.location = data.department
    package.note = (package.note + "；" if package.note else "") + f"发放：{data.department}（{operator}）"
    db.commit()
    db.refresh(package)
    return package


def use_package(db: Session, package_id: int, data, operator: str = "") -> PackageUsage:
    package = get_package(db, package_id)
    if not package:
        raise ValueError("器械包不存在")
    if package.status != "issued":
        raise ValueError("器械包未发放，不能登记使用")
    package.status = "used"
    row = PackageUsage(
        package_id=package.id,
        department=data.department,
        patient_id=data.patient_id,
        encounter_id=data.encounter_id,
        used_by=operator,
        note=data.note,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def recall_package(db: Session, package_id: int, reason: str = "", operator: str = "") -> InstrumentPackage:
    package = get_package(db, package_id)
    if not package:
        raise ValueError("器械包不存在")
    package.status = "recalled"
    package.note = (package.note + "；" if package.note else "") + f"召回：{reason or '未填写'}（{operator}）"
    db.commit()
    db.refresh(package)
    return package


def expiry_alerts(db: Session, days: int = 30) -> list[InstrumentPackage]:
    until = date.today() + timedelta(days=days)
    return (
        db.query(InstrumentPackage)
        .filter(
            InstrumentPackage.status == "sterilized",
            InstrumentPackage.expiry <= until,
        )
        .order_by(InstrumentPackage.expiry)
        .all()
    )
