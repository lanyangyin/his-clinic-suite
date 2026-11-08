from datetime import datetime

from sqlalchemy import DateTime, String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Encounter(Base):
    __tablename__ = "encounters"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    # 一次挂号对应一次就诊
    registration_id: Mapped[int] = mapped_column(
        ForeignKey("registrations.id"), unique=True, nullable=False, index=True
    )
    diagnosis: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="open", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, nullable=False
    )

    items: Mapped[list["PrescriptionItem"]] = relationship()


class PrescriptionItem(Base):
    __tablename__ = "prescription_items"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    encounter_id: Mapped[int] = mapped_column(
        ForeignKey("encounters.id"), nullable=False, index=True
    )
    drug_id: Mapped[int] = mapped_column(
        ForeignKey("drugs.id"), nullable=False, index=True
    )
    quantity: Mapped[int] = mapped_column(nullable=False)
    unit_price: Mapped[float] = mapped_column(nullable=False)
    # 用法用量：每次剂量 / 频次 / 给药途径 / 天数
    dosage: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    frequency: Mapped[str] = mapped_column(String(20), default="", nullable=False)
    route: Mapped[str] = mapped_column(String(20), default="", nullable=False)
    days: Mapped[int] = mapped_column(default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, nullable=False
    )
    # 医保事前提醒结果（warn 时记录提醒内容，pass 为 NULL）
    insurance_warning: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # 医保目录类别快照：甲/乙/丙（空=未对码）
    insurance_category: Mapped[str] = mapped_column(
        String(10), default="", server_default="", nullable=False
    )

    # 字符串关系：由同一 registry 解析，不跨模块 import models
    drug = relationship("Drug")

    @property
    def drug_name(self) -> str:
        return self.drug.name if self.drug else ""


class MedicalRecord(Base):
    __tablename__ = "medical_records"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    # 一次就诊一份病历（诊断沿用 encounter.diagnosis，不重复存储）
    encounter_id: Mapped[int] = mapped_column(
        ForeignKey("encounters.id"), nullable=False, unique=True, index=True
    )
    chief_complaint: Mapped[str] = mapped_column(String(200), nullable=False)
    present_illness: Mapped[str] = mapped_column(String(1000), default="", nullable=False)
    past_history: Mapped[str] = mapped_column(String(1000), default="", nullable=False)
    physical_exam: Mapped[str] = mapped_column(String(1000), default="", nullable=False)
    treatment_advice: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    written_by: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, nullable=False
    )
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # 电子签名：签名后病历锁定（不可再修改）
    signed_by: Mapped[str | None] = mapped_column(String(50), nullable=True)
    signed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
