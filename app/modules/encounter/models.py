from datetime import datetime

from sqlalchemy import DateTime, Integer, String, ForeignKey, Text
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
    diagnosis_code: Mapped[str] = mapped_column(
        String(20), default="", server_default="", nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), default="open", nullable=False)
    # initial 初诊 / follow_up 复诊，从挂号继承
    visit_type: Mapped[str] = mapped_column(
        String(20), default="initial", server_default="initial", nullable=False
    )
    # 复诊关联的上次就诊
    original_encounter_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, nullable=False
    )

    items: Mapped[list["PrescriptionItem"]] = relationship()
    prescriptions: Mapped[list["Prescription"]] = relationship(back_populates="encounter")


class EncounterDiagnosis(Base):
    """就诊诊断：按 sort_no 排序，第一条为主诊断。"""

    __tablename__ = "encounter_diagnoses"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    encounter_id: Mapped[int] = mapped_column(
        ForeignKey("encounters.id"), nullable=False, index=True
    )
    diagnosis_code: Mapped[str] = mapped_column(
        String(20), default="", server_default="", nullable=False
    )
    diagnosis: Mapped[str] = mapped_column(String(200), nullable=False)
    # primary 主诊断 / secondary 其他诊断，由排序自动生成
    diagnosis_type: Mapped[str] = mapped_column(
        String(20), default="primary", server_default="primary", nullable=False
    )
    # outpatient 门诊 / admission 入院 / discharge 出院
    diagnosis_stage: Mapped[str] = mapped_column(
        String(20), default="outpatient", server_default="outpatient", nullable=False
    )
    # initial 初步 / provisional 暂定 / corrected 修正 / final 最终
    diagnosis_phase: Mapped[str] = mapped_column(
        String(20), default="initial", server_default="initial", nullable=False
    )
    # pending 待查 / suspected 疑似 / confirmed 确诊
    diagnosis_certainty: Mapped[str] = mapped_column(
        String(20), default="confirmed", server_default="confirmed", nullable=False
    )
    sort_no: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    note: Mapped[str] = mapped_column(
        String(200), default="", server_default="", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, nullable=False
    )


class Prescription(Base):
    """一张处方头。处方明细必须挂在处方头下，不能直接挂就诊。"""

    __tablename__ = "prescriptions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    encounter_id: Mapped[int] = mapped_column(
        ForeignKey("encounters.id"), nullable=False, index=True
    )
    prescription_no: Mapped[str] = mapped_column(String(40), unique=True, nullable=False, index=True)
    # western 普通西药/中成药；tcm_herb 中药饮片；narcotic 麻精；special 特殊
    type: Mapped[str] = mapped_column(String(20), default="western", nullable=False)
    # pending_review 待审方 / approved 已通过 / rejected 已退回 / dispensing 调配中 / dispensed 已发药 / cancelled 已作废
    status: Mapped[str] = mapped_column(String(20), default="pending_review", nullable=False, index=True)
    prescribed_by: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    reviewed_by: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    review_note: Mapped[str] = mapped_column(String(300), default="", nullable=False)
    insurance_upload_status: Mapped[str] = mapped_column(
        String(20), default="not_ready", server_default="not_ready", nullable=False
    )
    insurance_uploaded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    encounter: Mapped["Encounter"] = relationship(back_populates="prescriptions")
    items: Mapped[list["PrescriptionItem"]] = relationship(
        back_populates="prescription", cascade="all, delete-orphan"
    )


class PrescriptionItem(Base):
    __tablename__ = "prescription_items"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    encounter_id: Mapped[int] = mapped_column(
        ForeignKey("encounters.id"), nullable=False, index=True
    )
    prescription_id: Mapped[int | None] = mapped_column(
        ForeignKey("prescriptions.id"), nullable=True, index=True
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
    # 过敏冲突：命中时记录冲突说明；医生 override 后记录理由和操作人
    allergy_warning: Mapped[str | None] = mapped_column(String(300), nullable=True)
    allergy_override_reason: Mapped[str | None] = mapped_column(
        String(300), nullable=True
    )
    allergy_override_by: Mapped[str | None] = mapped_column(String(50), nullable=True)
    prescription: Mapped["Prescription | None"] = relationship(back_populates="items")

    # 字符串关系：由同一 registry 解析，不跨模块 import models
    drug = relationship("Drug")

    @property
    def drug_name(self) -> str:
        return self.drug.name if self.drug else ""

    @property
    def prescription_no(self) -> str:
        return self.prescription.prescription_no if self.prescription else ""

    @property
    def prescription_type(self) -> str:
        return self.prescription.type if self.prescription else "western"

    @property
    def prescription_status(self) -> str:
        return self.prescription.status if self.prescription else "approved"


class PrescriptionLine(Base):
    """统一处方明细：西药/中成药 kind=drug，中药饮片 kind=herb。

    保留原明细表作为业务写模型，本表提供跨类型统一视图。
    """

    __tablename__ = "prescription_lines"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    prescription_id: Mapped[int] = mapped_column(
        ForeignKey("prescriptions.id"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(10), default="drug", nullable=False)
    drug_id: Mapped[int | None] = mapped_column(ForeignKey("drugs.id"), nullable=True)
    herb_id: Mapped[int | None] = mapped_column(ForeignKey("tcm_herbs.id"), nullable=True)
    source_item_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(100), default="", nullable=False)
    spec: Mapped[str] = mapped_column(String(60), default="", nullable=False)
    quantity: Mapped[float] = mapped_column(default=0.0, nullable=False)
    unit: Mapped[str] = mapped_column(String(20), default="", nullable=False)
    dosage: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    frequency: Mapped[str] = mapped_column(String(20), default="", nullable=False)
    route: Mapped[str] = mapped_column(String(20), default="", nullable=False)
    days: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    unit_price: Mapped[float] = mapped_column(default=0.0, nullable=False)
    amount: Mapped[float] = mapped_column(default=0.0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)


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
    personal_history: Mapped[str] = mapped_column(String(1000), default="", nullable=False)
    marital_history: Mapped[str] = mapped_column(String(1000), default="", nullable=False)
    family_history: Mapped[str] = mapped_column(String(1000), default="", nullable=False)
    physical_exam: Mapped[str] = mapped_column(String(1000), default="", nullable=False)
    auxiliary_exam: Mapped[str] = mapped_column(String(1000), default="", nullable=False)
    treatment_advice: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    written_by: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, nullable=False
    )
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # 电子签名：签名后病历锁定（不可再修改）
    signed_by: Mapped[str | None] = mapped_column(String(50), nullable=True)
    signed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)



class MedicalRecordRevision(Base):
    """病历签名后修订申请：医生提理由，管理员/院长审批后解锁。"""

    __tablename__ = "medical_record_revisions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    encounter_id: Mapped[int] = mapped_column(
        ForeignKey("encounters.id"), nullable=False, index=True
    )
    reason: Mapped[str] = mapped_column(String(300), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    requested_by: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    reviewed_by: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    review_note: Mapped[str] = mapped_column(String(300), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class MedicalRecordVersion(Base):
    """病历修改版本：签名前的每次保存都留 before/after 快照。"""

    __tablename__ = "medical_record_versions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    record_id: Mapped[int] = mapped_column(
        ForeignKey("medical_records.id"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    changed_by: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    action: Mapped[str] = mapped_column(String(20), default="update", nullable=False)
    before_json: Mapped[str] = mapped_column(Text, default="", nullable=False)
    after_json: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)


class AdverseReaction(Base):
    """药物不良反应/换药记录。"""

    __tablename__ = "adverse_reactions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    encounter_id: Mapped[int] = mapped_column(
        ForeignKey("encounters.id"), nullable=False, index=True
    )
    drug_name: Mapped[str] = mapped_column(String(100), default="", nullable=False)
    reaction: Mapped[str] = mapped_column(String(500), nullable=False)
    severity: Mapped[str] = mapped_column(
        String(20), default="moderate", nullable=False
    )
    action_taken: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    reported_by: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, nullable=False
    )
