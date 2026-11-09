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
    purchase_request_id: Mapped[int | None] = mapped_column(
        ForeignKey("purchase_requests.id"), nullable=True
    )

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
    # 已出库数量（支持部分出库）
    issued_quantity: Mapped[int] = mapped_column(
        default=0, server_default="0", nullable=False
    )
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


class StockAdjustment(Base):
    """盘点差异自动调整单（盘盈/盘亏）。"""

    __tablename__ = "stock_adjustments"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    adjust_no: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    kind: Mapped[str] = mapped_column(
        String(10), default="drug", server_default="drug", nullable=False
    )
    drug_id: Mapped[int | None] = mapped_column(ForeignKey("drugs.id"), nullable=True)
    material_id: Mapped[int | None] = mapped_column(
        ForeignKey("material_items.id"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    batch_no: Mapped[str] = mapped_column(
        String(30), default="", server_default="", nullable=False
    )
    expected_quantity: Mapped[int] = mapped_column(nullable=False)
    actual_quantity: Mapped[int] = mapped_column(nullable=False)
    diff: Mapped[int] = mapped_column(nullable=False)
    # in 盘盈 / out 盘亏
    direction: Mapped[str] = mapped_column(String(10), nullable=False)
    quantity: Mapped[int] = mapped_column(nullable=False)
    check_id: Mapped[int | None] = mapped_column(
        ForeignKey("warehouse_checks.id"), nullable=True
    )
    operator: Mapped[str] = mapped_column(
        String(50), default="", server_default="", nullable=False
    )
    note: Mapped[str] = mapped_column(
        String(200), default="", server_default="", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, nullable=False
    )

class PurchaseRequest(Base):
    """采购申请：库房缺货/补货时发起，需机构审核。"""

    __tablename__ = "purchase_requests"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    request_no: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    # outbound 出库缺货 / manual 手工补货 / min_stock 低库存
    source_type: Mapped[str] = mapped_column(
        String(20), default="manual", server_default="manual", nullable=False
    )
    source_id: Mapped[int | None] = mapped_column(nullable=True)
    department: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    # submitted 待审核 / approved 已批准 / ordered 已下单 / partially_received 部分到货
    # received 已入库 / rejected 已驳回 / cancelled 已取消
    status: Mapped[str] = mapped_column(
        String(20), default="submitted", server_default="submitted", nullable=False
    )
    total_amount: Mapped[float] = mapped_column(
        default=0.0, server_default="0", nullable=False
    )
    requester: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    approver: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    rejected_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    supplier_id: Mapped[int | None] = mapped_column(
        ForeignKey("suppliers.id"), nullable=True
    )
    ordered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    received_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    note: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)

    items: Mapped[list["PurchaseRequestItem"]] = relationship(
        back_populates="request", cascade="all, delete-orphan"
    )


class PurchaseRequestItem(Base):
    __tablename__ = "purchase_request_items"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    request_id: Mapped[int] = mapped_column(
        ForeignKey("purchase_requests.id"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(10), default="drug", nullable=False)
    drug_id: Mapped[int | None] = mapped_column(ForeignKey("drugs.id"), nullable=True)
    material_id: Mapped[int | None] = mapped_column(
        ForeignKey("material_items.id"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    spec: Mapped[str] = mapped_column(String(60), default="", nullable=False)
    unit: Mapped[str] = mapped_column(String(20), default="", nullable=False)
    quantity: Mapped[int] = mapped_column(nullable=False)
    received_quantity: Mapped[int] = mapped_column(
        default=0, server_default="0", nullable=False
    )
    estimated_unit_price: Mapped[float] = mapped_column(
        default=0.0, server_default="0", nullable=False
    )
    amount: Mapped[float] = mapped_column(default=0.0, server_default="0", nullable=False)
    batch_no: Mapped[str] = mapped_column(String(30), default="", nullable=False)
    expiry: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)

    request: Mapped[PurchaseRequest] = relationship(back_populates="items")
