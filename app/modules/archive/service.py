"""病案档案：建档、归档上架、借阅、复印、封存、销毁。"""
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.modules.encounter.service import get_encounter
from app.modules.patient.service import get_patient

from .models import (
    ArchiveBorrowing,
    ArchiveCopyRequest,
    ArchiveDestruction,
    ArchiveDestructionRequest,
    ArchiveRecord,
    ArchiveSeal,
)
from .schemas import (
    ArchiveCompleteRequest,
    ArchiveRecordCreate,
    BorrowCreate,
    CopyCompleteRequest,
    CopyCreate,
    DestroyCreate,
    DestructionDecision,
    DestructionExecute,
    DestructionRequestCreate,
    SealCreate,
)


def _next_archive_no(db: Session) -> str:
    last = db.query(ArchiveRecord.id).order_by(ArchiveRecord.id.desc()).first()
    return f"BA{datetime.now():%Y%m%d}{(last[0] if last else 0) + 1:04d}"


def create_record(
    db: Session, data: ArchiveRecordCreate, operator: str = ""
) -> ArchiveRecord:
    """病案建档：先登记，尚未上架归档。"""
    if not get_patient(db, data.patient_id):
        raise ValueError("患者不存在")
    if data.encounter_id is not None and not get_encounter(db, data.encounter_id):
        raise ValueError("就诊记录不存在")
    record = ArchiveRecord(
        patient_id=data.patient_id,
        encounter_id=data.encounter_id,
        record_type=data.record_type,
        page_count=data.page_count,
        storage_location=data.storage_location,
        note=data.note,
        status="draft",
        archived_by=operator,
    )
    db.add(record)
    db.flush()
    record.archive_no = _next_archive_no(db)
    db.commit()
    db.refresh(record)
    return record


def list_records(
    db: Session,
    archive_no: str | None = None,
    patient_id: int | None = None,
    status: str | None = None,
    record_type: str | None = None,
) -> list[ArchiveRecord]:
    query = db.query(ArchiveRecord)
    if archive_no:
        query = query.filter(ArchiveRecord.archive_no.like(f"%{archive_no}%"))
    if patient_id:
        query = query.filter(ArchiveRecord.patient_id == patient_id)
    if status:
        query = query.filter(ArchiveRecord.status == status)
    if record_type:
        query = query.filter(ArchiveRecord.record_type == record_type)
    return query.order_by(ArchiveRecord.id.desc()).all()


def get_record(db: Session, record_id: int) -> ArchiveRecord | None:
    return db.get(ArchiveRecord, record_id)


def archive_record(
    db: Session, record_id: int, data: ArchiveCompleteRequest, operator: str = ""
) -> ArchiveRecord:
    record = get_record(db, record_id)
    if not record:
        raise ValueError("病案不存在")
    if record.status != "draft":
        raise ValueError("该病案已归档或状态不可归档")
    if data.completeness == "incomplete":
        raise ValueError("完整性检查未通过，不能归档上架")
    record.page_count = data.page_count
    record.storage_location = data.storage_location
    record.completeness = data.completeness
    record.status = "archived"
    record.archived_at = datetime.now()
    record.archived_by = operator
    record.note = data.note or record.note
    db.commit()
    db.refresh(record)
    return record


def borrow_record(
    db: Session, record_id: int, data: BorrowCreate, approver: str = ""
) -> ArchiveBorrowing:
    record = get_record(db, record_id)
    if not record:
        raise ValueError("病案不存在")
    if record.status != "archived":
        raise ValueError("该病案未归档/已借出/已封存，不能借阅")
    row = ArchiveBorrowing(
        record_id=record.id,
        borrower=data.borrower,
        department=data.department,
        purpose=data.purpose,
        due_at=datetime.now().date() + timedelta(days=data.due_days),
        approver=approver,
        note=data.note,
    )
    record.status = "borrowed"
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def return_borrowing(
    db: Session, borrowing_id: int, operator: str = ""
) -> ArchiveBorrowing:
    row = db.get(ArchiveBorrowing, borrowing_id)
    if not row:
        raise ValueError("借阅记录不存在")
    if row.status == "returned":
        raise ValueError("该借阅已归还")
    row.status = "returned"
    row.returned_at = datetime.now()
    record = get_record(db, row.record_id)
    if record and record.status == "borrowed":
        record.status = "archived"
    db.commit()
    db.refresh(row)
    return row


def create_copy(db: Session, record_id: int, data: CopyCreate) -> ArchiveCopyRequest:
    record = get_record(db, record_id)
    if not record:
        raise ValueError("病案不存在")
    if record.status != "archived":
        raise ValueError("该病案当前不可复印（未归档/借出/封存/销毁）")
    row = ArchiveCopyRequest(
        record_id=record.id,
        applicant=data.applicant,
        id_number=data.id_number,
        relationship=data.relationship,
        purpose=data.purpose,
        contents=data.contents,
        copies=data.copies,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def complete_copy(
    db: Session, copy_id: int, data: CopyCompleteRequest, operator: str = ""
) -> ArchiveCopyRequest:
    row = db.get(ArchiveCopyRequest, copy_id)
    if not row:
        raise ValueError("复印申请不存在")
    if row.status == "completed":
        raise ValueError("该复印申请已完成")
    row.status = "completed"
    row.fee = data.fee
    row.operator = operator
    row.completed_at = datetime.now()
    db.commit()
    db.refresh(row)
    return row


def seal_record(
    db: Session, record_id: int, data: SealCreate, operator: str = ""
) -> ArchiveSeal:
    record = get_record(db, record_id)
    if not record:
        raise ValueError("病案不存在")
    if record.status != "archived":
        raise ValueError("该病案当前不可封存")
    record.status = "sealed"
    row = ArchiveSeal(
        record_id=record.id,
        action="seal",
        reason=data.reason,
        witness=data.witness,
        operator=operator,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def unseal_record(
    db: Session, record_id: int, data: SealCreate, operator: str = ""
) -> ArchiveSeal:
    record = get_record(db, record_id)
    if not record:
        raise ValueError("病案不存在")
    if record.status != "sealed":
        raise ValueError("该病案未封存")
    record.status = "archived"
    row = ArchiveSeal(
        record_id=record.id,
        action="unseal",
        reason=data.reason,
        witness=data.witness,
        operator=operator,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def destroy_record(
    db: Session, record_id: int, data: DestroyCreate, operator: str = ""
) -> ArchiveDestruction:
    record = get_record(db, record_id)
    if not record:
        raise ValueError("病案不存在")
    if record.status not in ("archived", "draft"):
        raise ValueError("该病案当前不可销毁")
    if not data.approved_by.strip():
        raise ValueError("销毁必须填写审批人")
    record.status = "destroyed"
    row = ArchiveDestruction(
        record_id=record.id,
        reason=data.reason,
        approved_by=data.approved_by,
        operator=operator,
        note=data.note,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def history(db: Session, record_id: int) -> dict:
    if not get_record(db, record_id):
        raise ValueError("病案不存在")
    return {
        "borrowings": db.query(ArchiveBorrowing)
        .filter(ArchiveBorrowing.record_id == record_id)
        .order_by(ArchiveBorrowing.id.desc())
        .all(),
        "copies": db.query(ArchiveCopyRequest)
        .filter(ArchiveCopyRequest.record_id == record_id)
        .order_by(ArchiveCopyRequest.id.desc())
        .all(),
        "seals": db.query(ArchiveSeal)
        .filter(ArchiveSeal.record_id == record_id)
        .order_by(ArchiveSeal.id.desc())
        .all(),
        "destructions": db.query(ArchiveDestruction)
        .filter(ArchiveDestruction.record_id == record_id)
        .order_by(ArchiveDestruction.id.desc())
        .all(),
    }


def create_destruction_request(
    db: Session, record_id: int, data: DestructionRequestCreate, operator: str = ""
) -> ArchiveDestructionRequest:
    record = get_record(db, record_id)
    if not record:
        raise ValueError("病案不存在")
    if record.status not in ("archived", "draft"):
        raise ValueError("该病案当前不可申请销毁")
    if record.active_borrowing:
        raise ValueError("病案借出中，不能申请销毁")
    pending = (
        db.query(ArchiveDestructionRequest)
        .filter(
            ArchiveDestructionRequest.record_id == record_id,
            ArchiveDestructionRequest.status.in_(("pending", "approved")),
        )
        .first()
    )
    if pending:
        raise ValueError("该病案已有未完成的销毁申请")
    row = ArchiveDestructionRequest(
        record_id=record_id,
        reason=data.reason.strip(),
        note=data.note.strip(),
        requested_by=operator,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def list_destruction_requests(
    db: Session, status: str | None = None
) -> list[ArchiveDestructionRequest]:
    query = db.query(ArchiveDestructionRequest)
    if status:
        query = query.filter(ArchiveDestructionRequest.status == status)
    return query.order_by(ArchiveDestructionRequest.id.desc()).all()


def decide_destruction_request(
    db: Session, request_id: int, approved: bool, data: DestructionDecision, approver: str
) -> ArchiveDestructionRequest:
    row = db.get(ArchiveDestructionRequest, request_id)
    if not row:
        raise ValueError("销毁申请不存在")
    if row.status != "pending":
        raise ValueError("该申请当前不可审批")
    row.status = "approved" if approved else "rejected"
    row.approver = approver
    row.approved_at = datetime.now()
    row.approval_note = data.note.strip()
    db.commit()
    db.refresh(row)
    return row


def execute_destruction_request(
    db: Session, request_id: int, data: DestructionExecute, operator: str
) -> ArchiveDestructionRequest:
    row = db.get(ArchiveDestructionRequest, request_id)
    if not row:
        raise ValueError("销毁申请不存在")
    if row.status != "approved":
        raise ValueError("销毁申请尚未批准")
    if data.witness.strip() == operator.strip():
        raise ValueError("执行人不能同时作为见证人")
    record = get_record(db, row.record_id)
    if not record:
        raise ValueError("病案不存在")
    if record.active_borrowing:
        raise ValueError("病案借出中，不能销毁")
    record.status = "destroyed"
    row.status = "executed"
    row.executed_by = operator
    row.executed_at = datetime.now()
    row.witness = data.witness.strip()
    db.add(
        ArchiveDestruction(
            record_id=record.id,
            reason=row.reason,
            approved_by=row.approver,
            operator=operator,
            note=f"{row.approval_note}；见证人：{row.witness}".strip("；"),
        )
    )
    db.commit()
    db.refresh(row)
    return row
