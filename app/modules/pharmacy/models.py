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
    verified_by: Mapped[str] = mapped_column(String(50), default="", server_default="", nullable=False)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    note: Mapped[str] = mapped_column(String(200), default="", server_default="", nullable=False)
    receiver_name: Mapped[str] = mapped_column(String(50), default="", server_default="", nullable=False)
    receiver_relation: Mapped[str] = mapped_column(String(20), default="本人", server_default="本人", nullable=False)
    signature_path: Mapped[str] = mapped_column(String(200), default="", server_default="", nullable=False)
    signed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


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

class PharmacyCall(Base):
    """药房叫号：一个就诊一条叫号记录。"""

    __tablename__ = "pharmacy_calls"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    encounter_id: Mapped[int] = mapped_column(
        ForeignKey("encounters.id"), unique=True, nullable=False, index=True
    )
    queue_no: Mapped[str] = mapped_column(String(20), nullable=False)
    # called 已叫号 / dispensed 已发药 / skipped 过号
    status: Mapped[str] = mapped_column(String(20), default="called", nullable=False)
    window_no: Mapped[str] = mapped_column(String(20), default="", nullable=False)
    called_by: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    called_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    note: Mapped[str] = mapped_column(String(200), default="", nullable=False)


class PharmacyPickupCode(Base):
    """取药码：患者凭码取药，药师扫码核对。"""

    __tablename__ = "pharmacy_pickup_codes"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    encounter_id: Mapped[int] = mapped_column(
        ForeignKey("encounters.id"), unique=True, nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
