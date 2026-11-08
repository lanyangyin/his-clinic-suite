from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class CACertificate(Base):
    __tablename__ = "ca_certificates"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    serial_no: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    subject: Mapped[str] = mapped_column(String(100), nullable=False)
    # 演示用密钥对（生产环境私钥应在加密机/UKey 内）
    private_key: Mapped[str] = mapped_column(String(64), nullable=False)
    public_key: Mapped[str] = mapped_column(String(128), nullable=False)
    # valid 有效 / revoked 已吊销
    status: Mapped[str] = mapped_column(String(20), default="valid", nullable=False)
    issued_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, nullable=False
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class CASeal(Base):
    __tablename__ = "ca_seals"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    certificate_id: Mapped[int] = mapped_column(
        ForeignKey("ca_certificates.id"), nullable=False
    )
    # 签章对象：medical_record 等
    target_type: Mapped[str] = mapped_column(String(30), nullable=False)
    target_id: Mapped[int] = mapped_column(nullable=False, index=True)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    signature: Mapped[str] = mapped_column(String(512), nullable=False)
    sealed_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "certificate_id", "target_type", "target_id", name="uq_ca_seal"
        ),
    )
