from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class Appointment(Base):
    """预约挂号：预约时占号，取号时生成挂号记录，爽约/取消释放号源。"""

    __tablename__ = "appointments"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    patient_id: Mapped[int] = mapped_column(
        ForeignKey("patients.id"), nullable=False, index=True
    )
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id"), nullable=False)
    schedule_id: Mapped[int] = mapped_column(
        ForeignKey("doctor_schedules.id"), nullable=False
    )
    registration_id: Mapped[int | None] = mapped_column(
        ForeignKey("registrations.id"), nullable=True
    )
    # booked 已预约 / checked_in 已取号 / no_show 爽约 / cancelled 已取消
    status: Mapped[str] = mapped_column(String(20), default="booked", nullable=False)
    created_by: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, nullable=False
    )
    checked_in_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
