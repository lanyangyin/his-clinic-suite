from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class SmsMessage(Base):
    """短信发送记录（Mock 网关：仅落库，不真实外发）。"""

    __tablename__ = "sms_messages"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(String(200), nullable=False)
    template: Mapped[str] = mapped_column(String(30), default="", nullable=False)
    # sent 已发送（Mock）/ failed 失败
    status: Mapped[str] = mapped_column(String(10), default="sent", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, nullable=False
    )
