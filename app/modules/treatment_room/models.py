from datetime import date as date_type, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String
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
    template_code: Mapped[str] = mapped_column(
        String(30), default="", server_default="", nullable=False
    )
    template_data: Mapped[str] = mapped_column(
        String(2000), default="", server_default="", nullable=False
    )
    diagnosis: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    # waiting 候诊 / in_progress 处置中 / completed 已完成 / cancelled 已取消
    status: Mapped[str] = mapped_column(String(20), default="waiting", nullable=False)
    priority: Mapped[str] = mapped_column(String(10), default="routine", nullable=False)
    charge_item_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    price: Mapped[float] = mapped_column(default=0.0, server_default="0", nullable=False)
    consent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    consent_version: Mapped[str] = mapped_column(
        String(20), default="v1", server_default="v1", nullable=False
    )
    consent_signer: Mapped[str] = mapped_column(
        String(50), default="", server_default="", nullable=False
    )
    consent_relation: Mapped[str] = mapped_column(
        String(20), default="", server_default="", nullable=False
    )
    consent_signature_path: Mapped[str] = mapped_column(
        String(200), default="", server_default="", nullable=False
    )
    consent_signed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    kit_applied: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0", nullable=False)
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

class TreatmentFollowUp(Base):
    """换药/拆线/复诊随访任务。"""

    __tablename__ = "treatment_follow_ups"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    case_id: Mapped[int | None] = mapped_column(
        ForeignKey("treatment_room_cases.id"), nullable=True, index=True
    )
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), nullable=False, index=True)
    encounter_id: Mapped[int | None] = mapped_column(ForeignKey("encounters.id"), nullable=True)
    due_date: Mapped[date_type] = mapped_column(Date, nullable=False, index=True)
    purpose: Mapped[str] = mapped_column(String(50), default="换药", nullable=False)
    # pending 待随访 / completed 已完成 / cancelled 已取消
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    note: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    result_note: Mapped[str] = mapped_column(String(500), default="", server_default="", nullable=False)
    healing_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    photo_path: Mapped[str] = mapped_column(String(200), default="", server_default="", nullable=False)
    completed_by: Mapped[str] = mapped_column(String(50), default="", server_default="", nullable=False)

    patient = relationship("Patient")
    case = relationship("TreatmentRoomCase")

    @property
    def patient_name(self) -> str:
        return self.patient.name if self.patient else ""

class TreatmentTemplateConfig(Base):
    """治疗室模板绑定：收费项目 + 一个套餐耗材。"""

    __tablename__ = "treatment_template_configs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    template_code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    charge_item_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    price: Mapped[float] = mapped_column(default=0.0, server_default="0", nullable=False)
    material_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    material_quantity: Mapped[int] = mapped_column(default=1, server_default="1", nullable=False)
    warehouse: Mapped[str] = mapped_column(String(30), default="总库", server_default="总库", nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1", nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)

class TreatmentTemplateMaterial(Base):
    __tablename__ = "treatment_template_materials"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    config_id: Mapped[int] = mapped_column(
        ForeignKey("treatment_template_configs.id"), nullable=False, index=True
    )
    material_id: Mapped[int] = mapped_column(ForeignKey("material_items.id"), nullable=False)
    quantity: Mapped[int] = mapped_column(default=1, server_default="1", nullable=False)
    warehouse: Mapped[str] = mapped_column(String(30), default="总库", server_default="总库", nullable=False)

    material = relationship("MaterialItem")


TreatmentTemplateConfig.materials = relationship(
    "TreatmentTemplateMaterial", cascade="all, delete-orphan"
)
