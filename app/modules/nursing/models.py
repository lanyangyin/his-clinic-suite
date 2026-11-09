from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class NursingOrder(Base):
    """护士执行单：由静滴/注射类处方或治疗单生成。"""

    __tablename__ = "nursing_orders"
    __table_args__ = (
        UniqueConstraint("source_type", "source_id", name="uq_nursing_source"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    encounter_id: Mapped[int] = mapped_column(
        ForeignKey("encounters.id"), nullable=False, index=True
    )
    source_type: Mapped[str] = mapped_column(String(20), nullable=False)  # prescription / treatment
    source_id: Mapped[int] = mapped_column(nullable=False)
    # infusion 输液 / injection 注射 / treatment 治疗
    order_type: Mapped[str] = mapped_column(String(20), default="infusion", nullable=False)
    item_name: Mapped[str] = mapped_column(String(100), nullable=False)
    dosage: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    route: Mapped[str] = mapped_column(String(30), default="", nullable=False)
    frequency: Mapped[str] = mapped_column(String(20), default="", nullable=False)
    # pending 待配药 / prepared 已配药 / executing 执行中 / completed 已完成 / skipped 已跳过
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    priority: Mapped[str] = mapped_column(String(10), default="routine", nullable=False)
    seat_no: Mapped[str] = mapped_column(String(20), default="", nullable=False)
    rate_ml_h: Mapped[float | None] = mapped_column(Float, nullable=True)
    prepared_by: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    prepared_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    executed_by: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    adverse_reaction: Mapped[str | None] = mapped_column(String(200), nullable=True)
    note: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)

    observations: Mapped[list["NursingObservation"]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )
    preparations: Mapped[list["NursingPreparation"]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )


class NursingPreparation(Base):
    __tablename__ = "nursing_preparations"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    order_id: Mapped[int] = mapped_column(
        ForeignKey("nursing_orders.id"), nullable=False, index=True
    )
    solvent: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    dose: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    batch_no: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    prepared_by: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    checked_by: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    prepared_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    note: Mapped[str] = mapped_column(String(200), default="", nullable=False)

    order: Mapped[NursingOrder] = relationship(back_populates="preparations")


class NursingObservation(Base):
    __tablename__ = "nursing_observations"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    order_id: Mapped[int] = mapped_column(
        ForeignKey("nursing_orders.id"), nullable=False, index=True
    )
    observed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    rate_ml_h: Mapped[float | None] = mapped_column(Float, nullable=True)
    note: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    adverse_reaction: Mapped[str | None] = mapped_column(String(200), nullable=True)
    nurse: Mapped[str] = mapped_column(String(50), default="", nullable=False)

    order: Mapped[NursingOrder] = relationship(back_populates="observations")
