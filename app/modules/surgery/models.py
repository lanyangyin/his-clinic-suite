from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class OperatingRoom(Base):
    __tablename__ = "operating_rooms"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    location: Mapped[str] = mapped_column(String(100), default="", nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class SurgeryCase(Base):
    __tablename__ = "surgery_cases"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    surgery_no: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), nullable=False, index=True)
    encounter_id: Mapped[int | None] = mapped_column(ForeignKey("encounters.id"), nullable=True)
    room_id: Mapped[int | None] = mapped_column(ForeignKey("operating_rooms.id"), nullable=True)
    procedure_name: Mapped[str] = mapped_column(String(100), nullable=False)
    diagnosis: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    surgeon: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    anesthesia_type: Mapped[str] = mapped_column(String(30), default="", nullable=False)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    # scheduled 已排班 / in_progress 手术中 / completed 已完成 / cancelled 已取消
    status: Mapped[str] = mapped_column(String(20), default="scheduled", nullable=False)
    notes: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    created_by: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    patient = relationship("Patient")
    room = relationship("OperatingRoom")
    checks: Mapped[list["SurgerySafetyCheck"]] = relationship(back_populates="case")
    records: Mapped[list["SurgeryRecord"]] = relationship(back_populates="case")
    counts: Mapped[list["SurgeryInstrumentCount"]] = relationship(back_populates="case")
    recovery: Mapped[list["SurgeryRecovery"]] = relationship(back_populates="case")

    @property
    def patient_name(self) -> str:
        return self.patient.name if self.patient else ""

    @property
    def room_name(self) -> str:
        return self.room.name if self.room else ""


class SurgerySafetyCheck(Base):
    __tablename__ = "surgery_safety_checks"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("surgery_cases.id"), nullable=False, index=True)
    phase: Mapped[str] = mapped_column(String(20), nullable=False)  # sign_in/time_out/sign_out
    checklist: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    completed_by: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)

    case: Mapped[SurgeryCase] = relationship(back_populates="checks")


class SurgeryRecord(Base):
    __tablename__ = "surgery_records"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("surgery_cases.id"), nullable=False, index=True)
    findings: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    procedure_detail: Mapped[str] = mapped_column(String(1000), default="", nullable=False)
    implants: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    specimens: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    blood_loss_ml: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    recorded_by: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)

    case: Mapped[SurgeryCase] = relationship(back_populates="records")


class SurgeryInstrumentCount(Base):
    __tablename__ = "surgery_instrument_counts"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("surgery_cases.id"), nullable=False, index=True)
    phase: Mapped[str] = mapped_column(String(20), nullable=False)  # before/after
    item_name: Mapped[str] = mapped_column(String(100), nullable=False)
    expected: Mapped[int] = mapped_column(default=0, nullable=False)
    actual: Mapped[int] = mapped_column(default=0, nullable=False)
    matched: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    counted_by: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    counted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)

    case: Mapped[SurgeryCase] = relationship(back_populates="counts")


class SurgeryRecovery(Base):
    __tablename__ = "surgery_recoveries"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("surgery_cases.id"), nullable=False, index=True)
    pacu_in: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    pacu_out: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    vitals: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    nurse: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    note: Mapped[str] = mapped_column(String(500), default="", nullable=False)

    case: Mapped[SurgeryCase] = relationship(back_populates="recovery")
