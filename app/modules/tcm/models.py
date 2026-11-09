from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class TcmHerb(Base):
    """中药饮片目录（单位克，按克计价）。"""

    __tablename__ = "tcm_herbs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    code: Mapped[str] = mapped_column(String(30), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    spec: Mapped[str] = mapped_column(String(60), default="", nullable=False)
    unit: Mapped[str] = mapped_column(String(10), default="g", nullable=False)
    price_per_g: Mapped[float] = mapped_column(default=0.0, server_default="0", nullable=False)
    insurance_code: Mapped[str] = mapped_column(String(40), default="", nullable=False)
    # none 普通 / toxic 毒性 / precious 贵重
    toxicity: Mapped[str] = mapped_column(String(20), default="none", nullable=False)
    note: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)


class TcmPrescription(Base):
    __tablename__ = "tcm_prescriptions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    prescription_no: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    encounter_id: Mapped[int] = mapped_column(
        ForeignKey("encounters.id"), nullable=False, index=True
    )
    doctor: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    formula_name: Mapped[str] = mapped_column(String(100), default="", nullable=False)
    usage: Mapped[str] = mapped_column(String(20), default="internal", nullable=False)
    packs: Mapped[int] = mapped_column(default=1, nullable=False)
    # decoct 代煎 / self 自煎
    decoct_service: Mapped[str] = mapped_column(String(10), default="decoct", nullable=False)
    decoction_method: Mapped[str] = mapped_column(String(50), default="常规煎煮", nullable=False)
    # pending 待审核 / reviewed 已审核 / dispensed 已发药 / decocting 煎药中 / completed 已完成 / cancelled
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    total_amount: Mapped[float] = mapped_column(default=0.0, server_default="0", nullable=False)
    review_by: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    dispense_by: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    dispensed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    note: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)

    items: Mapped[list["TcmPrescriptionItem"]] = relationship(
        back_populates="prescription", cascade="all, delete-orphan"
    )


class TcmPrescriptionItem(Base):
    __tablename__ = "tcm_prescription_items"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    prescription_id: Mapped[int] = mapped_column(
        ForeignKey("tcm_prescriptions.id"), nullable=False, index=True
    )
    herb_id: Mapped[int] = mapped_column(ForeignKey("tcm_herbs.id"), nullable=False)
    herb_name: Mapped[str] = mapped_column(String(100), nullable=False)
    dose_g: Mapped[float] = mapped_column(Float, nullable=False)
    special: Mapped[str] = mapped_column(String(20), default="none", nullable=False)
    note: Mapped[str] = mapped_column(String(100), default="", nullable=False)

    prescription: Mapped[TcmPrescription] = relationship(back_populates="items")
    herb: Mapped[TcmHerb] = relationship()


class DecoctionOrder(Base):
    __tablename__ = "decoction_orders"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    order_no: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    prescription_id: Mapped[int] = mapped_column(
        ForeignKey("tcm_prescriptions.id"), nullable=False, unique=True
    )
    encounter_id: Mapped[int] = mapped_column(
        ForeignKey("encounters.id"), nullable=False, index=True
    )
    patient_name: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    # received 已接方 / soaking 浸泡 / decocting 煎煮 / packaging 包装 / completed 已完成 / issued 已发放
    status: Mapped[str] = mapped_column(String(20), default="received", nullable=False)
    soak_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    decoct_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    machine_no: Mapped[str] = mapped_column(String(30), default="", nullable=False)
    operator: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    bags: Mapped[int] = mapped_column(default=0, server_default="0", nullable=False)
    bag_volume_ml: Mapped[int | None] = mapped_column(Integer, nullable=True)
    received_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    soaked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    decocted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    packaged_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    pickup_method: Mapped[str] = mapped_column(String(20), default="self", nullable=False)
    receiver: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    issued_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    note: Mapped[str] = mapped_column(String(200), default="", nullable=False)

    bags_list: Mapped[list["DecoctionBag"]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )


class DecoctionBag(Base):
    __tablename__ = "decoction_bags"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    order_id: Mapped[int] = mapped_column(
        ForeignKey("decoction_orders.id"), nullable=False, index=True
    )
    bag_no: Mapped[str] = mapped_column(String(50), nullable=False)
    expiry: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    label: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)

    order: Mapped[DecoctionOrder] = relationship(back_populates="bags_list")
