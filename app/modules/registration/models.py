from datetime import date

from sqlalchemy import Date, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class DoctorSchedule(Base):
    __tablename__ = "doctor_schedules"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    doctor_id: Mapped[int] = mapped_column(
        ForeignKey("doctors.id"), nullable=False, index=True
    )
    schedule_date: Mapped[date] = mapped_column(Date, nullable=False)
    # morning 上午 / afternoon 下午
    period: Mapped[str] = mapped_column(String(10), nullable=False)
    capacity: Mapped[int] = mapped_column(nullable=False)
    booked: Mapped[int] = mapped_column(default=0, nullable=False)
    # 出诊诊室（可选）
    room_id: Mapped[int | None] = mapped_column(
        ForeignKey("rooms.id"), nullable=True
    )


class Registration(Base):
    __tablename__ = "registrations"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    patient_id: Mapped[int] = mapped_column(
        ForeignKey("patients.id"), nullable=False, index=True
    )
    # Doctor 表还没建，先用整数占位，不加外键
    doctor_id: Mapped[int] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="registered", nullable=False)
    # 号源排班（可空：不指定排班时为自由挂号，保持兼容）
    schedule_id: Mapped[int | None] = mapped_column(
        ForeignKey("doctor_schedules.id"), nullable=True, index=True
    )
    # initial 初诊 / follow_up 复诊
    visit_type: Mapped[str] = mapped_column(
        String(20), default="initial", server_default="initial", nullable=False
    )
    # 复诊关联的上次挂号（可空）
    original_registration_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
