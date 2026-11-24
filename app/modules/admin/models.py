from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class RefundExportTemplate(Base):
    """退费留痕导出字段模板。"""

    __tablename__ = "refund_export_templates"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    fields: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_by: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)


class FinancialVoucher(Base):
    """财务凭证：按收费/退费/住院缴费生成，业务键唯一防重复。"""

    __tablename__ = "financial_vouchers"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    voucher_no: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    biz_type: Mapped[str] = mapped_column(String(20), nullable=False)
    biz_id: Mapped[int] = mapped_column(nullable=False)
    amount: Mapped[float] = mapped_column(nullable=False)
    direction: Mapped[str] = mapped_column(String(10), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)


class FinancialReconciliation(Base):
    """财务日对账签收（操作人+时间，非 CA 签章）。"""

    __tablename__ = "financial_reconciliations"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    biz_date: Mapped[str] = mapped_column(String(10), unique=True, nullable=False)
    total_payment: Mapped[float] = mapped_column(nullable=False)
    total_inpatient: Mapped[float] = mapped_column(nullable=False)
    total_refund: Mapped[float] = mapped_column(nullable=False)
    net: Mapped[float] = mapped_column(nullable=False)
    operator: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
