from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class TriageTicket(Base):
    __tablename__ = "triage_tickets"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    # 一个挂号对应一张叫号单
    registration_id: Mapped[int] = mapped_column(
        ForeignKey("registrations.id"), nullable=False, unique=True, index=True
    )
    # waiting 候诊 / called 已叫号 / passed 已过号 / done 已完成
    status: Mapped[str] = mapped_column(String(20), default="waiting", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, nullable=False
    )
    called_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    passed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    done_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
