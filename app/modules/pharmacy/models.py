from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Dispense(Base):
    __tablename__ = "dispensations"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    # MVP：一次就诊只发一次药
    encounter_id: Mapped[int] = mapped_column(
        ForeignKey("encounters.id"), unique=True, nullable=False, index=True
    )
    # dispensed 已发药 / returned 已退药
    status: Mapped[str] = mapped_column(
        String(10), default="dispensed", nullable=False
    )
    returned_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class DrugStock(Base):
    __tablename__ = "drug_stocks"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    drug_id: Mapped[int] = mapped_column(
        ForeignKey("drugs.id"), nullable=False, index=True
    )
    batch_no: Mapped[str] = mapped_column(String(30), nullable=False)
    expiry: Mapped[date] = mapped_column(Date, nullable=False)
    location: Mapped[str] = mapped_column(String(20), default="", nullable=False)
    quantity: Mapped[int] = mapped_column(nullable=False)

    __table_args__ = (
        UniqueConstraint("drug_id", "batch_no", name="uq_drug_stocks_drug_batch"),
    )

    drug = relationship("Drug")
