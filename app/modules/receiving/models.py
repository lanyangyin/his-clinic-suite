from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class InboundOrder(Base):
    """入库单：收货 → 验收 → 入库（药品/器械/耗材/办公用品统一入口）。"""

    __tablename__ = "inbound_orders"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    order_no: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    # drug 药品 / device 器械 / consumable 耗材 / office 办公用品 / other
    order_type: Mapped[str] = mapped_column(
        String(20), default="drug", server_default="drug", nullable=False
    )
    supplier_id: Mapped[int | None] = mapped_column(
        ForeignKey("suppliers.id"), nullable=True
    )
    # purchase 采购 / return 退货入库 / donation 捐赠 / transfer 调拨
    source: Mapped[str] = mapped_column(
        String(20), default="purchase", server_default="purchase", nullable=False
    )
    # received 已收货 / checked 已验收 / stocked 已入库 / cancelled 已取消
    status: Mapped[str] = mapped_column(
        String(20), default="received", server_default="received", nullable=False
    )
    delivery_no: Mapped[str] = mapped_column(
        String(50), default="", server_default="", nullable=False
    )
    invoice_no: Mapped[str] = mapped_column(
        String(50), default="", server_default="", nullable=False
    )
    received_by: Mapped[str] = mapped_column(
        String(50), default="", server_default="", nullable=False
    )
    checked_by: Mapped[str] = mapped_column(
        String(50), default="", server_default="", nullable=False
    )
    received_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    checked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    stocked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    note: Mapped[str] = mapped_column(
        String(200), default="", server_default="", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, nullable=False
    )

    items: Mapped[list["InboundItem"]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )


class InboundItem(Base):
    __tablename__ = "inbound_items"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    order_id: Mapped[int] = mapped_column(
        ForeignKey("inbound_orders.id"), nullable=False, index=True
    )
    # drug 药品 / material 物资（器械/耗材/办公）
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
    # 医保贯标码（药品）/ 器械注册证号
    insurance_code: Mapped[str] = mapped_column(
        String(40), default="", server_default="", nullable=False
    )
    insurance_name: Mapped[str] = mapped_column(
        String(100), default="", server_default="", nullable=False
    )
    insurance_category: Mapped[str] = mapped_column(
        String(20), default="未对码", server_default="未对码", nullable=False
    )
    insurance_match_status: Mapped[str] = mapped_column(
        String(20), default="unmatched", server_default="unmatched", nullable=False
    )
    dosage_form: Mapped[str] = mapped_column(
        String(30), default="", server_default="", nullable=False
    )
    approval_no: Mapped[str] = mapped_column(
        String(60), default="", server_default="", nullable=False
    )
    registration_no: Mapped[str] = mapped_column(
        String(60), default="", server_default="", nullable=False
    )
    manufacturer: Mapped[str] = mapped_column(
        String(100), default="", server_default="", nullable=False
    )
    # 常温 / 阴凉 / 冷藏
    storage_condition: Mapped[str] = mapped_column(
        String(20), default="", server_default="", nullable=False
    )
    # 物资入库库房（药品入库走药房批次库存，不使用该字段）
    warehouse: Mapped[str] = mapped_column(
        String(30), default="总库", server_default="总库", nullable=False
    )
    # 药品货位
    location: Mapped[str] = mapped_column(
        String(20), default="", server_default="", nullable=False
    )
    rejected_qty: Mapped[int] = mapped_column(
        default=0, server_default="0", nullable=False
    )
    reject_reason: Mapped[str] = mapped_column(
        String(200), default="", server_default="", nullable=False
    )
    note: Mapped[str] = mapped_column(
        String(200), default="", server_default="", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, nullable=False
    )

    order: Mapped["InboundOrder"] = relationship(back_populates="items")
