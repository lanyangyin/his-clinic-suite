"""GSP：验收、温湿度/养护、不良反应、召回、人员资质。"""
from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from app.modules.supplier.service import get_supplier

from .models import (
    GspAcceptance,
    GspAcceptanceItem,
    GspAdverseReaction,
    GspPersonnel,
    GspRecall,
    GspStorageLog,
)
from .schemas import (
    AcceptanceCreate,
    AdverseCreate,
    PersonnelCreate,
    RecallCreate,
    StorageLogCreate,
)


def _next_no(db: Session, model, prefix: str) -> str:
    last = db.query(model.id).order_by(model.id.desc()).first()
    return f"{prefix}{datetime.now():%Y%m%d}{(last[0] if last else 0) + 1:04d}"


def create_acceptance(db: Session, data: AcceptanceCreate, operator: str = "") -> GspAcceptance:
    supplier_name = data.supplier_name
    if data.supplier_id is not None:
        supplier = get_supplier(db, data.supplier_id)
        if not supplier:
            raise ValueError("供应商不存在")
        supplier_name = supplier.name
    if not data.transport_ok:
        data.result = "unqualified"
    acceptance = GspAcceptance(
        acceptance_no=_next_no(db, GspAcceptance, "GSPA"),
        supplier_id=data.supplier_id,
        supplier_name=supplier_name,
        delivery_no=data.delivery_no,
        transport_temp=data.transport_temp,
        transport_ok=data.transport_ok,
        result=data.result,
        accepted_by=operator,
        note=data.note,
    )
    db.add(acceptance)
    db.flush()
    for item in data.items:
        db.add(
            GspAcceptanceItem(
                acceptance_id=acceptance.id,
                kind=item.kind,
                name=item.name,
                spec=item.spec,
                batch_no=item.batch_no,
                expiry=item.expiry,
                quantity=item.quantity,
                manufacturer=item.manufacturer,
                approval_no=item.approval_no,
                result=item.result,
                note=item.note,
            )
        )
    db.commit()
    db.refresh(acceptance)
    return acceptance


def list_acceptances(db: Session) -> list[GspAcceptance]:
    return db.query(GspAcceptance).order_by(GspAcceptance.id.desc()).all()


def create_storage_log(db: Session, data: StorageLogCreate, operator: str = "") -> GspStorageLog:
    result = "normal"
    if data.log_type == "temperature":
        if data.temperature is not None and not (10 <= data.temperature <= 30):
            result = "abnormal"
        if data.humidity is not None and not (35 <= data.humidity <= 75):
            result = "abnormal"
    row = GspStorageLog(
        log_type=data.log_type,
        area=data.area,
        temperature=data.temperature,
        humidity=data.humidity,
        equipment=data.equipment,
        result=result,
        operator=operator,
        note=data.note,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def list_storage_logs(db: Session) -> list[GspStorageLog]:
    return db.query(GspStorageLog).order_by(GspStorageLog.id.desc()).all()


def create_adverse(db: Session, data: AdverseCreate, operator: str = "") -> GspAdverseReaction:
    row = GspAdverseReaction(**data.model_dump(), reported_by=operator)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def list_adverse(db: Session) -> list[GspAdverseReaction]:
    return db.query(GspAdverseReaction).order_by(GspAdverseReaction.id.desc()).all()


def create_recall(db: Session, data: RecallCreate, operator: str = "") -> GspRecall:
    row = GspRecall(
        recall_no=_next_no(db, GspRecall, "GSPR"),
        drug_name=data.drug_name,
        batch_no=data.batch_no,
        reason=data.reason,
        level=data.level,
        operator=operator,
        note=data.note,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def list_recalls(db: Session) -> list[GspRecall]:
    return db.query(GspRecall).order_by(GspRecall.id.desc()).all()


def complete_recall(db: Session, recall_id: int, operator: str = "") -> GspRecall:
    row = db.get(GspRecall, recall_id)
    if not row:
        raise ValueError("召回不存在")
    if row.status == "completed":
        raise ValueError("该召回已完成")
    row.status = "completed"
    row.completed_at = datetime.now()
    row.operator = operator or row.operator
    db.commit()
    db.refresh(row)
    return row


def create_personnel(db: Session, data: PersonnelCreate) -> GspPersonnel:
    status = "expired" if data.valid_until and data.valid_until < date.today() else "active"
    row = GspPersonnel(**data.model_dump(), status=status)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def list_personnel(db: Session) -> list[GspPersonnel]:
    return db.query(GspPersonnel).order_by(GspPersonnel.id.desc()).all()


def alerts(db: Session) -> dict:
    soon = date.today() + timedelta(days=30)
    return {
        "unqualified_acceptances": [
            row for row in list_acceptances(db) if row.result == "unqualified"
        ],
        "abnormal_storage": [
            row for row in list_storage_logs(db) if row.result == "abnormal"
        ],
        "active_recalls": [row for row in list_recalls(db) if row.status == "initiated"],
        "expiring_personnel": [
            row
            for row in list_personnel(db)
            if row.valid_until is not None and row.valid_until <= soon
        ],
        "serious_adverse": [
            row for row in list_adverse(db) if row.severity == "severe"
        ],
    }
