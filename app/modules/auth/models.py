from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    salt: Mapped[str] = mapped_column(String(64), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    display_name: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    employee_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    doctor_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # 麻醉/第一类精神药品处方权；管理员默认放行，普通医生需显式授予
    narcotic_right: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0", nullable=False)
    # 账号是否启用；离职/停用后禁止登录
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1", nullable=False)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(50), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    method: Mapped[str] = mapped_column(String(10), nullable=False)
    path: Mapped[str] = mapped_column(String(200), nullable=False)
    status_code: Mapped[int] = mapped_column(nullable=False)
    ip: Mapped[str] = mapped_column(String(45), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, nullable=False
    )
