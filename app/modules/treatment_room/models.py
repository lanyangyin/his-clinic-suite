from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class TreatmentRoom(Base):
    __tablename__ = "treatment_rooms"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    location: Mapped[str] = mapped_column(String(100), default="", nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class TreatmentRoomCase(Base):
    __tablename__ = "treatment_room_cases"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    case_no: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), nullable=False, index=True)
    encounter_id: Mapped[int | None] = mapped_column(ForeignKey("encounters.id"), nullable=True)
    room_id: Mapped[int | None] = mapped_column(ForeignKey("treatment_rooms.id"), nullable=True)
    treatment_order_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    procedure_name: Mapped[str] = mapped_column(String(100), nullable=False)
    diagnosis: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    # waiting 候诊 / in_progress 处置中 / completed 已完成 / cancelled 已取消
    status: Mapped[str] = mapped_column(String(20), default="waiting", nullable=False)
    priority: Mapped[str] = mapped_column(String(10), default="routine", nullable=False)
    charge_item_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    price: Mapped[float] = mapped_column(default=0.0, server_default="0", nullable=False)
    consent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    anesthesia: Mapped[str] = mapped_column(String(100), default="", nullable=False)
    findings: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    procedure_detail: Mapped[str] = mapped_column(String(1000), default="", nullable=False)
    sutures: Mapped[str] = mapped_column(String(100), default="", nullable=False)
    dressing: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    materials: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    complications: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    operator: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    requested_by: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    note: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)

    patient = relationship("Patient")
    room = relationship("TreatmentRoom")

    @property
    def patient_name(self) -> str:
        return self.patient.name if self.patient else ""

    @property
    def room_name(self) -> str:
        return self.room.name if self.room else ""
