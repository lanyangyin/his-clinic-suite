from datetime import datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.registration.service import get_registration

from .models import TriageTicket
from .schemas import TicketCreate


def create_ticket(
    db: Session, data: TicketCreate, operator: str = ""
) -> TriageTicket:
    """挂号后入分诊队列：同一挂号只能有一张叫号单，并记录预检分诊。"""
    registration_id = data.registration_id
    if not get_registration(db, registration_id):
        raise ValueError("挂号记录不存在")

    existing = (
        db.query(TriageTicket)
        .filter(TriageTicket.registration_id == registration_id)
        .first()
    )
    if existing:
        raise ValueError("该挂号已在分诊队列中")

    ticket = TriageTicket(
        registration_id=registration_id,
        status="waiting",
        triage_level=data.triage_level,
        chief_complaint=data.chief_complaint,
        temperature=data.temperature,
        pulse=data.pulse,
        respiration=data.respiration,
        systolic=data.systolic,
        diastolic=data.diastolic,
        spo2=data.spo2,
        pain_score=data.pain_score,
        isolation=data.isolation,
        assessed_by=operator,
        assessed_at=datetime.now(),
    )
    db.add(ticket)
    try:
        db.commit()
    except IntegrityError:
        # 并发入队兜底：registration_id 唯一约束
        db.rollback()
        raise ValueError("该挂号已在分诊队列中")
    db.refresh(ticket)
    return ticket


def get_ticket(db: Session, ticket_id: int) -> TriageTicket | None:
    return db.get(TriageTicket, ticket_id)


def list_queue(db: Session, status: str = "waiting") -> list[TriageTicket]:
    """分诊队列（默认候诊，按入队顺序）。"""
    return (
        db.query(TriageTicket)
        .filter(TriageTicket.status == status)
        .order_by(TriageTicket.id)
        .all()
    )


def call_ticket(db: Session, ticket_id: int) -> TriageTicket:
    """叫号：仅候诊中的叫号单可叫。"""
    ticket = get_ticket(db, ticket_id)
    if not ticket:
        raise ValueError("叫号单不存在")
    if ticket.status != "waiting":
        raise ValueError("仅候诊中的叫号单可以叫号")

    ticket.status = "called"
    ticket.called_at = datetime.now()
    db.commit()
    db.refresh(ticket)
    return ticket


def pass_ticket(db: Session, ticket_id: int) -> TriageTicket:
    """过号：已叫号但未到诊的患者跳过。"""
    ticket = get_ticket(db, ticket_id)
    if not ticket:
        raise ValueError("叫号单不存在")
    if ticket.status != "called":
        raise ValueError("仅已叫号的叫号单可以过号")

    ticket.status = "passed"
    ticket.passed_at = datetime.now()
    db.commit()
    db.refresh(ticket)
    return ticket


def complete_ticket_for_registration(db: Session, registration_id: int) -> None:
    """接诊时自动完成分诊（只改内存，由调用方统一 commit）。"""
    ticket = (
        db.query(TriageTicket)
        .filter(
            TriageTicket.registration_id == registration_id,
            TriageTicket.status.in_(["waiting", "called"]),
        )
        .first()
    )
    if ticket:
        ticket.status = "done"
        ticket.done_at = datetime.now()
