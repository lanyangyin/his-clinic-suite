from datetime import date, datetime

from sqlalchemy import Date, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class InsuranceDrug(Base):
    """医保药品目录（贯标码 + 甲乙类 + 限定支付范围）。"""

    __tablename__ = "insurance_drugs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    # 国家医保药品代码（贯标码）
    national_code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    dosage_form: Mapped[str] = mapped_column(
        String(30), default="", server_default="", nullable=False
    )
    spec: Mapped[str] = mapped_column(
        String(60), default="", server_default="", nullable=False
    )
    manufacturer: Mapped[str] = mapped_column(
        String(100), default="", server_default="", nullable=False
    )
    unit: Mapped[str] = mapped_column(
        String(20), default="", server_default="", nullable=False
    )
    # 甲类 / 乙类 / 丙类（丙类=目录外自费，演示用）
    category: Mapped[str] = mapped_column(
        String(10), default="乙", server_default="乙", nullable=False
    )
    reimbursement_note: Mapped[str] = mapped_column(
        String(200), default="", server_default="", nullable=False
    )
    approval_no: Mapped[str] = mapped_column(
        String(60), default="", server_default="", nullable=False
    )
    valid_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    valid_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    source_version: Mapped[str] = mapped_column(
        String(30), default="", server_default="", nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, nullable=False
    )


class InsuranceCatalogVersion(Base):
    """目录导入版本（手动导入/自动同步各留痕）。"""

    __tablename__ = "insurance_catalog_versions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    version: Mapped[str] = mapped_column(String(30), nullable=False)
    source: Mapped[str] = mapped_column(
        String(20), default="manual", server_default="manual", nullable=False
    )
    file_name: Mapped[str] = mapped_column(
        String(200), default="", server_default="", nullable=False
    )
    row_count: Mapped[int] = mapped_column(
        default=0, server_default="0", nullable=False
    )
    checksum: Mapped[str] = mapped_column(
        String(64), default="", server_default="", nullable=False
    )
    imported_by: Mapped[str] = mapped_column(
        String(50), default="", server_default="", nullable=False
    )
    imported_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, nullable=False
    )
