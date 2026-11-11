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


class RetailSale(Base):
    """药房零售：OTC 药品/耗材直接销售，不建就诊。"""

    __tablename__ = "retail_sales"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    sale_no: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    customer_name: Mapped[str] = mapped_column(
        String(50), default="", server_default="", nullable=False
    )
    phone: Mapped[str] = mapped_column(
        String(20), default="", server_default="", nullable=False
    )
    channel: Mapped[str] = mapped_column(
        String(20), default="cash", server_default="cash", nullable=False
    )
    total_amount: Mapped[float] = mapped_column(
        default=0.0, server_default="0", nullable=False
    )
    # completed 已完成 / refunded 已退货
    status: Mapped[str] = mapped_column(
        String(20), default="completed", server_default="completed", nullable=False
    )
    sold_by: Mapped[str] = mapped_column(
        String(50), default="", server_default="", nullable=False
    )
    refunded_by: Mapped[str] = mapped_column(
        String(50), default="", server_default="", nullable=False
    )
    refunded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, nullable=False
    )

    items: Mapped[list["RetailSaleItem"]] = relationship(
        back_populates="sale", cascade="all, delete-orphan"
    )


class RetailSaleItem(Base):
    __tablename__ = "retail_sale_items"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    sale_id: Mapped[int] = mapped_column(
        ForeignKey("retail_sales.id"), nullable=False, index=True
    )
    # drug 药品 / material 耗材
    kind: Mapped[str] = mapped_column(String(10), nullable=False)
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
    warehouse: Mapped[str] = mapped_column(
        String(30), default="药房", server_default="药房", nullable=False
    )
    quantity: Mapped[int] = mapped_column(nullable=False)
    unit_price: Mapped[float] = mapped_column(
        default=0.0, server_default="0", nullable=False
    )
    amount: Mapped[float] = mapped_column(
        default=0.0, server_default="0", nullable=False
    )

    sale: Mapped[RetailSale] = relationship(back_populates="items")
