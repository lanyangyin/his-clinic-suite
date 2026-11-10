from datetime import datetime

from sqlalchemy import DateTime, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class CashierShift(Base):
    __tablename__ = "cashier_shifts"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    shift_no: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    cashier: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    opened_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    opening_float: Mapped[float] = mapped_column(default=0.0, server_default="0", nullable=False)
    counted_cash: Mapped[float | None] = mapped_column(Float, nullable=True)
    expected_cash: Mapped[float | None] = mapped_column(Float, nullable=True)
    difference: Mapped[float | None] = mapped_column(Float, nullable=True)
    # open 交班中 / closed 已交班
    status: Mapped[str] = mapped_column(String(20), default="open", nullable=False)
    note: Mapped[str] = mapped_column(String(200), default="", nullable=False)
