from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
class WarehouseStock(Base):
    __tablename__ = "warehouse_stocks"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    drug_id: Mapped[int] = mapped_column(
        ForeignKey("drugs.id"), nullable=False, index=True
    )
    batch_no: Mapped[str] = mapped_column(String(30), nullable=False)
    expiry: Mapped[date] = mapped_column(Date, nullable=False)
    quantity: Mapped[int] = mapped_column(default=0, server_default="0", nullable=False)

    __table_args__ = (
        UniqueConstraint("drug_id", "batch_no", name="uq_warehouse_drug_batch"),
    )

    drug = relationship("Drug")

    @property
    def drug_name(self) -> str:
        return self.drug.name if self.drug else ""


class WarehouseCheck(Base):
    __tablename__ = "warehouse_checks"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    drug_id: Mapped[int] = mapped_column(
        ForeignKey("drugs.id"), nullable=False, index=True
    )
    batch_no: Mapped[str] = mapped_column(String(30), nullable=False)
    expected_quantity: Mapped[int] = mapped_column(nullable=False)
    actual_quantity: Mapped[int] = mapped_column(nullable=False)
    diff: Mapped[int] = mapped_column(nullable=False)
    checked_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, nullable=False
    )
    checked_by: Mapped[str] = mapped_column(String(50), default="", nullable=False)


class PurchaseRecord(Base):
    __tablename__ = "purchase_records"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    drug_id: Mapped[int] = mapped_column(
        ForeignKey("drugs.id"), nullable=False, index=True
    )
    batch_no: Mapped[str] = mapped_column(String(30), nullable=False)
    quantity: Mapped[int] = mapped_column(nullable=False)
    # 供应商可选：未指定时为空
    supplier_id: Mapped[int | None] = mapped_column(
        ForeignKey("suppliers.id"), nullable=True
    )
    purchased_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, nullable=False
    )
    purchased_by: Mapped[str] = mapped_column(String(50), default="", nullable=False)

    drug = relationship("Drug")
    supplier = relationship("Supplier")

    @property
    def drug_name(self) -> str:
        return self.drug.name if self.drug else ""

    @property
    def supplier_name(self) -> str:
        return self.supplier.name if self.supplier else ""
