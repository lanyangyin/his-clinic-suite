from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class InvoiceOperation(Base):
    """发票打印/作废留痕。"""

    __tablename__ = "invoice_operations"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    payment_id: Mapped[int] = mapped_column(
        ForeignKey("payments.id"), nullable=False, index=True
    )
    invoice_no: Mapped[str] = mapped_column(String(30), default="", nullable=False)
    # print 打印 / void 作废
    action: Mapped[str] = mapped_column(String(20), nullable=False)
    operator: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    reason: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
