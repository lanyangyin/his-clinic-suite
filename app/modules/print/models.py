from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PrintToken(Base):
    """打印一次性令牌：短时有效、使用一次，避免把 Basic 凭据放进打印 URL。"""

    __tablename__ = "print_tokens"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(30), default="", nullable=False)
    ref_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_by: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
