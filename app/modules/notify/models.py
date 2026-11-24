from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class NotificationOutbox(Base):
    """审批通知出站队列：先落库，再由派发器发送，失败可重试。"""

    __tablename__ = "notification_outbox"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    biz_type: Mapped[str] = mapped_column(String(30), default="", nullable=False)
    biz_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    channel: Mapped[str] = mapped_column(String(20), default="internal", nullable=False)
    recipient: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    title: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    body: Mapped[str] = mapped_column(Text, default="", nullable=False)
    # pending / sent / failed / read
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False, index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error: Mapped[str] = mapped_column(String(300), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
