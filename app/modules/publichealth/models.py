from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class DiseaseReport(Base):
    __tablename__ = "disease_reports"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    encounter_id: Mapped[int] = mapped_column(
        ForeignKey("encounters.id"), nullable=False, index=True
    )
    disease_code: Mapped[str] = mapped_column(String(20), nullable=False)
    disease_name: Mapped[str] = mapped_column(String(100), nullable=False)
    # draft 草稿 / submitted 已上报
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, nullable=False
    )
    reported_by: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint("encounter_id", "disease_code", name="uq_disease_report"),
    )
