from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class ClinicalPathway(Base):
    __tablename__ = "clinical_pathways"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    diagnosis: Mapped[str] = mapped_column(String(200), nullable=False)


class PathwayEnrollment(Base):
    __tablename__ = "pathway_enrollments"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    pathway_id: Mapped[int] = mapped_column(
        ForeignKey("clinical_pathways.id"), nullable=False
    )
    admission_id: Mapped[int] = mapped_column(
        ForeignKey("admissions.id"), nullable=False, index=True
    )
    # active 进行中 / completed 已完成 / withdrawn 已退出
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    enrolled_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint("pathway_id", "admission_id", name="uq_pathway_admission"),
    )


class PathwayVariance(Base):
    __tablename__ = "pathway_variances"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    enrollment_id: Mapped[int] = mapped_column(
        ForeignKey("pathway_enrollments.id"), nullable=False, index=True
    )
    reason: Mapped[str] = mapped_column(String(200), nullable=False)
    noted_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, nullable=False
    )
    noted_by: Mapped[str] = mapped_column(String(50), default="", nullable=False)
