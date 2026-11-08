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


class OutboundOrder(Base):
    """出库单：库房向药房/科室出库（申请 → 审核 → 出库）。"""

    __tablename__ = "outbound_orders"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    outbound_no: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    # requisition 领用 / transfer 调拨 / scrap 报损 / return 退库
    outbound_type: Mapped[str] = mapped_column(
        String(20), default="requisition", server_default="requisition", nullable=False
    )
    # pharmacy 药房 / department 科室
    target_type: Mapped[str] = mapped_column(
        String(20), default="pharmacy", server_default="pharmacy", nullable=False
    )
    target_name: Mapped[str] = mapped_column(
        String(50), default="药房", server_default="药房", nullable=False
    )
    applicant: Mapped[str] = mapped_column(
        String(50), default="", server_default="", nullable=False
    )
    approver: Mapped[str] = mapped_column(
        String(50), default="", server_default="", nullable=False
    )
    issuer: Mapped[str] = mapped_column(
        String(50), default="", server_default="", nullable=False
    )
    # submitted 已申请 / approved 已审核 / issued 已出库 / cancelled 已取消
    status: Mapped[str] = mapped_column(
        String(20), default="submitted", server_default="submitted", nullable=False
    )
    note: Mapped[str] = mapped_column(
        String(200), default="", server_default="", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, nullable=False
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    issued_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    items: Mapped[list["OutboundItem"]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )


class OutboundItem(Base):
    __tablename__ = "outbound_items"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    order_id: Mapped[int] = mapped_column(
        ForeignKey("outbound_orders.id"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(
        String(10), default="drug", server_default="drug", nullable=False
    )
    drug_id: Mapped[int | None] = mapped_column(ForeignKey("drugs.id"), nullable=True)
    material_id: Mapped[int | None] = mapped_column(
        ForeignKey("material_items.id"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    spec: Mapped[str] = mapped_column(
        String(60), default="", server_default="", nullable=False
    )
    unit: Mapped[str] = mapped_column(
        String(20), default="", server_default="", nullable=False
    )
    batch_no: Mapped[str] = mapped_column(
        String(30), default="", server_default="", nullable=False
    )
    expiry: Mapped[date | None] = mapped_column(Date, nullable=True)
    quantity: Mapped[int] = mapped_column(nullable=False)
    unit_price: Mapped[float] = mapped_column(
        default=0.0, server_default="0", nullable=False
    )
    amount: Mapped[float] = mapped_column(
        default=0.0, server_default="0", nullable=False
    )
    insurance_code: Mapped[str] = mapped_column(
        String(40), default="", server_default="", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, nullable=False
    )

    order: Mapped["OutboundOrder"] = relationship(back_populates="items")
