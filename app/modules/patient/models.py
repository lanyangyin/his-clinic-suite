from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

class Patient(Base):
    __tablename__ = "patients"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    patient_no: Mapped[str | None] = mapped_column(
        String(20), unique=True, index=True, nullable=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    id_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="id_card", server_default="id_card"
    )
    id_number: Mapped[str | None] = mapped_column(
        String(30), unique=True, index=True, nullable=True
    )
    gender: Mapped[str] = mapped_column(
        String(10), nullable=False, default="unknown", server_default="unknown"
    )
    birth_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    address: Mapped[str] = mapped_column(
        String(200), nullable=False, default="", server_default=""
    )
    emergency_contact_name: Mapped[str] = mapped_column(
        String(50), nullable=False, default="", server_default=""
    )
    emergency_contact_relation: Mapped[str] = mapped_column(
        String(20), nullable=False, default="", server_default=""
    )
    emergency_contact_phone: Mapped[str] = mapped_column(
        String(20), nullable=False, default="", server_default=""
    )
    insurance_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="self_pay", server_default="self_pay"
    )
    allergy_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="unknown", server_default="unknown"
    )
    allergy_detail: Mapped[str] = mapped_column(
        String(200), nullable=False, default="", server_default=""
    )
    # 特殊既往病史/慢病：糖尿病、高血压、冠心病等，患者级长期信息
    special_history: Mapped[str] = mapped_column(
        String(500), nullable=False, default="", server_default=""
    )
    privacy_consent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="normal", server_default="normal"
    )
    merged_into_id: Mapped[int | None] = mapped_column(
        ForeignKey("patients.id"), nullable=True
    )
    created_by: Mapped[str] = mapped_column(
        String(50), nullable=False, default="", server_default=""
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now, server_default="CURRENT_TIMESTAMP"
    )
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_by: Mapped[str] = mapped_column(
        String(50), nullable=False, default="", server_default=""
    )

    @property
    def age(self) -> int | None:
        if not self.birth_date:
            return None
        today = date.today()
        return today.year - self.birth_date.year - (
            (today.month, today.day) < (self.birth_date.month, self.birth_date.day)
        )

    @property
    def allergy_label(self) -> str:
        if self.allergy_status == "none":
            return "无过敏史"
        if self.allergy_status == "present":
            return self.allergy_detail or "有过敏史"
        return "过敏史不详"

class PatientCard(Base):
    """NFC 就诊卡：一张卡同一时间只能绑定一个患者。"""

    __tablename__ = "patient_cards"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    patient_id: Mapped[int] = mapped_column(
        ForeignKey("patients.id"), nullable=False, index=True
    )
    card_uid: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, nullable=False
    )
    # active 正常 / lost 挂失 / replaced 已换卡
    status: Mapped[str] = mapped_column(
        String(20), default="active", server_default="active", nullable=False
    )
    issued_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, nullable=False
    )
    issued_by: Mapped[str] = mapped_column(
        String(50), default="", server_default="", nullable=False
    )
    note: Mapped[str] = mapped_column(
        String(200), default="", server_default="", nullable=False
    )



class PatientClinicalChange(Base):
    """医生修改患者级过敏史/现存疾病的审计记录。"""

    __tablename__ = "patient_clinical_changes"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    patient_id: Mapped[int] = mapped_column(
        ForeignKey("patients.id"), nullable=False, index=True
    )
    field: Mapped[str] = mapped_column(String(30), nullable=False)
    old_value: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    new_value: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    reason: Mapped[str] = mapped_column(String(300), default="", nullable=False)
    changed_by: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    changed_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, nullable=False
    )
