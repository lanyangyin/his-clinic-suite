from sqlalchemy.orm import Session

from .models import InvoiceBatch
from .schemas import InvoiceBatchCreate


def create_batch(db: Session, data: InvoiceBatchCreate) -> InvoiceBatch:
    if data.end_no < data.start_no:
        raise ValueError("结束号不能小于开始号")
    overlap = (
        db.query(InvoiceBatch)
        .filter(
            InvoiceBatch.prefix == data.prefix,
            InvoiceBatch.status == "active",
            InvoiceBatch.start_no <= data.end_no,
            InvoiceBatch.end_no >= data.start_no,
            InvoiceBatch.assigned_to == data.assigned_to,
        )
        .first()
    )
    if overlap:
        raise ValueError("号段与现有号段重叠")
    row = InvoiceBatch(
        prefix=data.prefix,
        start_no=data.start_no,
        end_no=data.end_no,
        next_no=data.start_no,
        assigned_to=data.assigned_to,
        note=data.note,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def list_batches(db: Session, status: str | None = None) -> list[InvoiceBatch]:
    query = db.query(InvoiceBatch)
    if status:
        query = query.filter(InvoiceBatch.status == status)
    return query.order_by(InvoiceBatch.id.desc()).all()


def close_batch(db: Session, batch_id: int) -> InvoiceBatch:
    row = db.get(InvoiceBatch, batch_id)
    if not row:
        raise ValueError("号段不存在")
    row.status = "closed"
    db.commit()
    db.refresh(row)
    return row


def allocate(db: Session, cashier: str) -> InvoiceBatch | None:
    """为收费员分配一个可用发票号；无可用号段返回 None。"""
    query = (
        db.query(InvoiceBatch)
        .filter(
            InvoiceBatch.status == "active",
            InvoiceBatch.next_no <= InvoiceBatch.end_no,
            InvoiceBatch.assigned_to.in_(("", cashier)),
        )
        .order_by(InvoiceBatch.id)
    )
    for batch in query.all():
        if batch.next_no > batch.end_no:
            continue
        batch.next_no += 1
        if batch.next_no > batch.end_no:
            batch.status = "closed"
        db.flush()
        return batch
    return None
