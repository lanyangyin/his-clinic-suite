from datetime import date, datetime

from sqlalchemy import Date, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class FinanceClosure(Base):
    __tablename__ = "finance_closures"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    close_date: Mapped[date] = mapped_column(Date, unique=True, nullable=False)
    outpatient_paid_count: Mapped[int] = mapped_column(default=0, nullable=False)
    outpatient_paid_amount: Mapped[float] = mapped_column(default=0.0, nullable=False)
    outpatient_refunded_count: Mapped[int] = mapped_column(default=0, nullable=False)
    outpatient_refunded_amount: Mapped[float] = mapped_column(default=0.0, nullable=False)
    insurance_amount: Mapped[float] = mapped_column(default=0.0, nullable=False)
    inpatient_charge_count: Mapped[int] = mapped_column(default=0, nullable=False)
    inpatient_charge_amount: Mapped[float] = mapped_column(default=0.0, nullable=False)
    closed_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, nullable=False
    )
    closed_by: Mapped[str] = mapped_column(String(50), default="", nullable=False)
