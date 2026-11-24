from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
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
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class NotificationTemplate(Base):
    """通知模板：管理台维护标题/正文/渠道。"""

    __tablename__ = "notification_templates"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    body: Mapped[str] = mapped_column(Text, default="", nullable=False)
    channel: Mapped[str] = mapped_column(String(20), default="internal", nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class NotificationRead(Base):
    """按用户记录已读，避免 role 行一人已读全角色已读。"""

    __tablename__ = "notification_reads"
    __table_args__ = (
        __import__("sqlalchemy").UniqueConstraint("notification_id", "username", name="uq_notification_user_read"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    notification_id: Mapped[int] = mapped_column(
        ForeignKey("notification_outbox.id"), nullable=False, index=True
    )
    username: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    read_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
