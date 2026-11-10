from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class InvoiceBatch(Base):
    """发票号段：按收费员分配，收费时顺序占用。"""

    __tablename__ = "invoice_batches"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    prefix: Mapped[str] = mapped_column(String(20), default="INV", nullable=False)
    start_no: Mapped[int] = mapped_column(Integer, nullable=False)
    end_no: Mapped[int] = mapped_column(Integer, nullable=False)
    next_no: Mapped[int] = mapped_column(Integer, nullable=False)
    # 空=公共号段；否则仅该收费员可用
    assigned_to: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    # active 使用中 / closed 已用完/停用
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    note: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
