"""被服洗涤消毒：批次、发放、召回、窗帘拆洗。与器械灭菌完全分开。"""
from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from .models import CurtainRecord, LinenBatch, LinenDistribution


def _next_batch_no(db: Session) -> str:
    last = db.query(LinenBatch.id).order_by(LinenBatch.id.desc()).first()
    return f"LIN{datetime.now():%Y%m%d}{(last[0] if last else 0) + 1:04d}"


def create_batch(db: Session, data, created_by: str = "") -> LinenBatch:
    batch_no = (getattr(data, "batch_no", None) or "").strip() or _next_batch_no(db)
    if db.query(LinenBatch).filter(LinenBatch.batch_no == batch_no).first():
        raise ValueError("被服批次号已存在")
    batch = LinenBatch(
        batch_no=batch_no,
        category=data.category,
        item_name=data.item_name,
        quantity=data.quantity,
        unit=data.unit,
        source_department=data.source_department,
        soil_level=data.soil_level,
        wash_method=data.wash_method,
        temperature=data.temperature,
        duration_min=data.duration_min,
        detergent=data.detergent,
        operator=data.operator,
        washed_at=data.washed_at or datetime.now(),
        note=data.note,
        created_by=created_by,
    )
    db.add(batch)
    db.commit()
    db.refresh(batch)
    return batch


def list_batches(
    db: Session,
    category: str | None = None,
    status: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[LinenBatch]:
    query = db.query(LinenBatch)
    if category:
        query = query.filter(LinenBatch.category == category)
    if status:
        query = query.filter(LinenBatch.status == status)
    if start_date:
        query = query.filter(LinenBatch.washed_at >= datetime.combine(start_date, datetime.min.time()))
    if end_date:
        query = query.filter(LinenBatch.washed_at < datetime.combine(end_date + timedelta(days=1), datetime.min.time()))
    return query.order_by(LinenBatch.id.desc()).all()


def get_batch(db: Session, batch_id: int) -> LinenBatch | None:
    return db.get(LinenBatch, batch_id)


def distribute(
    db: Session, batch_id: int, data, distributed_by: str = ""
) -> LinenDistribution:
    batch = get_batch(db, batch_id)
    if not batch:
        raise ValueError("被服批次不存在")
    if batch.status == "recalled":
        raise ValueError("该批次已召回，不能发放")
    if data.quantity > batch.remaining_quantity:
        raise ValueError(f"发放数量超过剩余数量 {batch.remaining_quantity}")
    row = LinenDistribution(
        batch_id=batch.id,
        department=data.department,
        quantity=data.quantity,
        distributed_by=distributed_by,
        note=data.note,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def recall(db: Session, batch_id: int, reason: str = "", operator: str = "") -> LinenBatch:
    batch = get_batch(db, batch_id)
    if not batch:
        raise ValueError("被服批次不存在")
    batch.status = "recalled"
    batch.note = (batch.note + "；" if batch.note else "") + f"召回：{reason or '未填写原因'}（{operator}）"
    db.commit()
    db.refresh(batch)
    return batch


def create_curtain(db: Session, data) -> CurtainRecord:
    row = CurtainRecord(
        department=data.department,
        room=data.room,
        curtain_no=data.curtain_no,
        event=data.event,
        event_at=data.event_at or datetime.now(),
        method=data.method,
        operator=data.operator,
        next_due=data.next_due,
        note=data.note,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def list_curtains(db: Session, department: str | None = None) -> list[CurtainRecord]:
    query = db.query(CurtainRecord)
    if department:
        query = query.filter(CurtainRecord.department == department)
    return query.order_by(CurtainRecord.id.desc()).all()


def curtain_reminders(db: Session, days: int = 30) -> list[CurtainRecord]:
    until = date.today() + timedelta(days=days)
    return (
        db.query(CurtainRecord)
        .filter(CurtainRecord.next_due.isnot(None), CurtainRecord.next_due <= until)
        .order_by(CurtainRecord.next_due)
        .all()
    )


def summary(db: Session, start_date: date, end_date: date) -> dict:
    rows = list_batches(db, start_date=start_date, end_date=end_date)
    by_category: dict[str, int] = {}
    for row in rows:
        by_category[row.category] = by_category.get(row.category, 0) + row.quantity
    return {
        "start_date": start_date,
        "end_date": end_date,
        "batch_count": len(rows),
        "total_quantity": sum(row.quantity for row in rows),
        "distributed_quantity": sum(row.distributed_quantity for row in rows),
        "recalled_count": sum(1 for row in rows if row.status == "recalled"),
        "by_category": by_category,
    }
