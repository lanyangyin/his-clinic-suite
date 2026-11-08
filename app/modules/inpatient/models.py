from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Ward(Base):
    __tablename__ = "wards"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)


class Bed(Base):
    __tablename__ = "beds"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    ward_id: Mapped[int] = mapped_column(
        ForeignKey("wards.id"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    # empty 空闲 / occupied 占用
    status: Mapped[str] = mapped_column(String(20), default="empty", nullable=False)

    __table_args__ = (
        UniqueConstraint("ward_id", "code", name="uq_beds_ward_code"),
    )


class Admission(Base):
    __tablename__ = "admissions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    patient_id: Mapped[int] = mapped_column(
        ForeignKey("patients.id"), nullable=False, index=True
    )
    doctor_id: Mapped[int] = mapped_column(
        ForeignKey("doctors.id"), nullable=False
    )
    bed_id: Mapped[int] = mapped_column(
        ForeignKey("beds.id"), nullable=False, index=True
    )
    # in 在院 / discharged 已出院
    status: Mapped[str] = mapped_column(String(20), default="in", nullable=False)
    admitted_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, nullable=False
    )
    discharged_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class InpatientOrder(Base):
    __tablename__ = "inpatient_orders"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    admission_id: Mapped[int] = mapped_column(
        ForeignKey("admissions.id"), nullable=False, index=True
    )
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id"), nullable=False)
    drug_id: Mapped[int] = mapped_column(ForeignKey("drugs.id"), nullable=False)
    # standing 长期医嘱 / stat 临时医嘱
    order_type: Mapped[str] = mapped_column(String(20), nullable=False)
    quantity: Mapped[int] = mapped_column(nullable=False)
    # open 执行中 / stopped 已停止 / finished 已完成
    status: Mapped[str] = mapped_column(String(20), default="open", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, nullable=False
    )

    drug = relationship("Drug")

    @property
    def drug_name(self) -> str:
        return self.drug.name if self.drug else ""


class OrderExecution(Base):
    __tablename__ = "order_executions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    order_id: Mapped[int] = mapped_column(
        ForeignKey("inpatient_orders.id"), nullable=False, index=True
    )
    executed_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, nullable=False
    )
    note: Mapped[str] = mapped_column(String(200), default="", nullable=False)


class InpatientCharge(Base):
    __tablename__ = "inpatient_charges"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    admission_id: Mapped[int] = mapped_column(
        ForeignKey("admissions.id"), nullable=False, index=True
    )
    # 一次执行对应一条费用（唯一约束防重复计费）
    execution_id: Mapped[int] = mapped_column(
        ForeignKey("order_executions.id"), nullable=False, unique=True, index=True
    )
    quantity: Mapped[int] = mapped_column(nullable=False)
    unit_price: Mapped[float] = mapped_column(nullable=False)
    amount: Mapped[float] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, nullable=False
    )


class InpatientDispenseRequest(Base):
    __tablename__ = "inpatient_dispense_requests"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    admission_id: Mapped[int] = mapped_column(
        ForeignKey("admissions.id"), nullable=False, index=True
    )
    order_id: Mapped[int] = mapped_column(
        ForeignKey("inpatient_orders.id"), nullable=False, index=True
    )
    drug_id: Mapped[int] = mapped_column(ForeignKey("drugs.id"), nullable=False)
    quantity: Mapped[int] = mapped_column(nullable=False)
    # pending 待摆药 / dispensed 已发药 / returned 已退药
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, nullable=False
    )
    dispensed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    returned_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    drug = relationship("Drug")

    @property
    def drug_name(self) -> str:
        return self.drug.name if self.drug else ""


class VitalSign(Base):
    __tablename__ = "vital_signs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    admission_id: Mapped[int] = mapped_column(
        ForeignKey("admissions.id"), nullable=False, index=True
    )
    temperature: Mapped[float | None] = mapped_column(nullable=True)
    pulse: Mapped[int | None] = mapped_column(nullable=True)
    respiration: Mapped[int | None] = mapped_column(nullable=True)
    systolic: Mapped[int | None] = mapped_column(nullable=True)
    diastolic: Mapped[int | None] = mapped_column(nullable=True)
    spo2: Mapped[int | None] = mapped_column(nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, nullable=False
    )
    recorded_by: Mapped[str] = mapped_column(String(50), default="", nullable=False)


class NursingNote(Base):
    __tablename__ = "nursing_notes"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    admission_id: Mapped[int] = mapped_column(
        ForeignKey("admissions.id"), nullable=False, index=True
    )
    content: Mapped[str] = mapped_column(String(500), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, nullable=False
    )
    recorded_by: Mapped[str] = mapped_column(String(50), default="", nullable=False)
