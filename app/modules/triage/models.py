from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class TriageTicket(Base):
    __tablename__ = "triage_tickets"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    # 一个挂号对应一张叫号单
    registration_id: Mapped[int] = mapped_column(
        ForeignKey("registrations.id"), nullable=False, unique=True, index=True
    )
    # waiting 候诊 / called 已叫号 / passed 已过号 / done 已完成
    status: Mapped[str] = mapped_column(String(20), default="waiting", nullable=False)
    # 预检分诊：1 级濒危 / 2 级危重 / 3 级急症 / 4 级非急症
    triage_level: Mapped[int] = mapped_column(
        Integer, default=4, server_default="4", nullable=False
    )
    chief_complaint: Mapped[str] = mapped_column(
        String(200), default="", server_default="", nullable=False
    )
    temperature: Mapped[float | None] = mapped_column(Float, nullable=True)
    pulse: Mapped[int | None] = mapped_column(Integer, nullable=True)
    respiration: Mapped[int | None] = mapped_column(Integer, nullable=True)
    systolic: Mapped[int | None] = mapped_column(Integer, nullable=True)
    diastolic: Mapped[int | None] = mapped_column(Integer, nullable=True)
    spo2: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pain_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    isolation: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="0", nullable=False
    )
    assessed_by: Mapped[str] = mapped_column(
        String(50), default="", server_default="", nullable=False
    )
    assessed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, nullable=False
    )
    called_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    passed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    done_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    @property
    def bp_display(self) -> str:
        if self.systolic is None or self.diastolic is None:
            return ""
        return f"{self.systolic}/{self.diastolic}"

    @property
    def vital_summary(self) -> str:
        parts = []
        if self.temperature is not None:
            parts.append(f"T {self.temperature:g}℃")
        if self.pulse is not None:
            parts.append(f"P {self.pulse}")
        if self.respiration is not None:
            parts.append(f"R {self.respiration}")
        if self.bp_display:
            parts.append(f"BP {self.bp_display}")
        if self.spo2 is not None:
            parts.append(f"SpO2 {self.spo2}%")
        return " · ".join(parts)
