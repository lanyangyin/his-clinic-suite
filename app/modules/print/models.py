from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text
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


class PrintLog(Base):
    """打印流水：谁在何时打印了什么文档，用于补打/审计。"""

    __tablename__ = "print_logs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    document_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    ref_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    operator: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)


class PrintProfile(Base):
    """机构级打印外观配置（单例 id=1）。"""

    __tablename__ = "print_profile"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    clinic_name: Mapped[str] = mapped_column(String(100), default="", nullable=False)
    clinic_address: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    clinic_phone: Mapped[str] = mapped_column(String(40), default="", nullable=False)
    logo_url: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    theme_color: Mapped[str] = mapped_column(String(20), default="#111111", nullable=False)
    font_family: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    paper_size: Mapped[str] = mapped_column(String(10), default="A4", nullable=False)
    margin_mm: Mapped[int] = mapped_column(default=12, nullable=False)
    header_note: Mapped[str] = mapped_column(String(300), default="", nullable=False)
    footer_note: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    doctor_label: Mapped[str] = mapped_column(String(30), default="医师", nullable=False)
    reviewer_label: Mapped[str] = mapped_column(String(30), default="审核药师", nullable=False)
    dispenser_label: Mapped[str] = mapped_column(String(30), default="调配药师", nullable=False)
    checker_label: Mapped[str] = mapped_column(String(30), default="核对、发药药师", nullable=False)
    custom_css: Mapped[str] = mapped_column(Text, default="", nullable=False)
    updated_by: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
