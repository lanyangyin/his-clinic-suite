from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class GspAcceptance(Base):
    """药品/耗材验收记录（运输温度、到货、验收结论）。"""

    __tablename__ = "gsp_acceptances"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    acceptance_no: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    supplier_id: Mapped[int | None] = mapped_column(ForeignKey("suppliers.id"), nullable=True)
    supplier_name: Mapped[str] = mapped_column(String(100), default="", nullable=False)
    delivery_no: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    arrival_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    transport_temp: Mapped[float | None] = mapped_column(Float, nullable=True)
    transport_ok: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    result: Mapped[str] = mapped_column(String(20), default="qualified", nullable=False)
    accepted_by: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    note: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)

    items: Mapped[list["GspAcceptanceItem"]] = relationship(
        back_populates="acceptance", cascade="all, delete-orphan"
    )


class GspAcceptanceItem(Base):
    __tablename__ = "gsp_acceptance_items"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    acceptance_id: Mapped[int] = mapped_column(
        ForeignKey("gsp_acceptances.id"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(10), default="drug", nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    spec: Mapped[str] = mapped_column(String(60), default="", nullable=False)
    batch_no: Mapped[str] = mapped_column(String(30), default="", nullable=False)
    expiry: Mapped[date | None] = mapped_column(Date, nullable=True)
    quantity: Mapped[int] = mapped_column(default=0, nullable=False)
    manufacturer: Mapped[str] = mapped_column(String(100), default="", nullable=False)
    approval_no: Mapped[str] = mapped_column(String(60), default="", nullable=False)
    result: Mapped[str] = mapped_column(String(20), default="qualified", nullable=False)
    note: Mapped[str] = mapped_column(String(200), default="", nullable=False)

    acceptance: Mapped[GspAcceptance] = relationship(back_populates="items")


class GspStorageLog(Base):
    """温湿度、养护、陈列环境记录。"""

    __tablename__ = "gsp_storage_logs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    log_type: Mapped[str] = mapped_column(String(20), default="temperature", nullable=False)
    area: Mapped[str] = mapped_column(String(50), default="药房", nullable=False)
    temperature: Mapped[float | None] = mapped_column(Float, nullable=True)
    humidity: Mapped[float | None] = mapped_column(Float, nullable=True)
    equipment: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    result: Mapped[str] = mapped_column(String(20), default="normal", nullable=False)
    operator: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    note: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)


class GspAdverseReaction(Base):
    __tablename__ = "gsp_adverse_reactions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    patient_name: Mapped[str] = mapped_column(String(50), nullable=False)
    drug_name: Mapped[str] = mapped_column(String(100), nullable=False)
    batch_no: Mapped[str] = mapped_column(String(30), default="", nullable=False)
    reaction: Mapped[str] = mapped_column(String(200), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), default="mild", nullable=False)
    reported_by: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    reported_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    # reported 已报告 / investigating 调查中 / closed 已结案
    status: Mapped[str] = mapped_column(String(20), default="reported", nullable=False)


class GspRecall(Base):
    __tablename__ = "gsp_recalls"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    recall_no: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    drug_name: Mapped[str] = mapped_column(String(100), nullable=False)
    batch_no: Mapped[str] = mapped_column(String(30), default="", nullable=False)
    reason: Mapped[str] = mapped_column(String(200), nullable=False)
    level: Mapped[str] = mapped_column(String(10), default="3", nullable=False)
    # initiated 已启动 / completed 已完成
    status: Mapped[str] = mapped_column(String(20), default="initiated", nullable=False)
    initiated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    operator: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    note: Mapped[str] = mapped_column(String(200), default="", nullable=False)


class GspPersonnel(Base):
    __tablename__ = "gsp_personnel"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    role: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    certificate_no: Mapped[str] = mapped_column(String(60), default="", nullable=False)
    valid_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    training_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    note: Mapped[str] = mapped_column(String(200), default="", nullable=False)
