from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PortalLoginCode(Base):
    """患者门户短信验证码：短时有效、一次性、限尝试次数。"""

    __tablename__ = "portal_login_codes"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    id_number: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    code_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
