from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class EncounterCreate(BaseModel):
    registration_id: int
    diagnosis: str = ""
    diagnosis_code: str = ""


class EncounterResponse(EncounterCreate):
    id: int
    status: str
    visit_type: str = "initial"
    original_encounter_id: int | None = None
    model_config = ConfigDict(from_attributes=True)


class BarcodeLookup(BaseModel):
    encounter_id: int
    patient_id: int
    patient_name: str
    code: str
    code_type: str
    is_paid: bool
    is_dispensed: bool
    pending_amount: float
    status_text: str


class DiagnosisUpdate(BaseModel):
    diagnosis_code: str = ""
    diagnosis: str = ""


class PrescriptionItemCreate(BaseModel):
    drug_id: int
    quantity: int = Field(gt=0)
    # 用法用量（中大型门诊处方必备）：每次剂量 / 频次 / 给药途径 / 天数
    dosage: str = Field(default="", max_length=50)
    frequency: str = Field(default="", max_length=20)
    route: str = Field(default="", max_length=20)
    days: int = Field(default=1, ge=1, le=365)
    # 过敏冲突时医生填写理由后强制放行，服务端留痕
    allergy_override_reason: str = Field(default="", max_length=300)


class PrescriptionItemResponse(BaseModel):
    id: int
    encounter_id: int
    drug_id: int
    drug_name: str
    quantity: int
    unit_price: float
    dosage: str
    frequency: str
    route: str
    days: int
    insurance_warning: str | None = None
    insurance_category: str = ""
    allergy_warning: str | None = None
    allergy_override_reason: str | None = None
    allergy_override_by: str | None = None
    model_config = ConfigDict(from_attributes=True)


class MedicalRecordCreate(BaseModel):
    chief_complaint: str = Field(min_length=1, max_length=200)
    present_illness: str = Field(default="", max_length=1000)
    past_history: str = Field(default="", max_length=1000)
    personal_history: str = Field(default="", max_length=1000)
    marital_history: str = Field(default="", max_length=1000)
    family_history: str = Field(default="", max_length=1000)
    physical_exam: str = Field(default="", max_length=1000)
    auxiliary_exam: str = Field(default="", max_length=1000)
    treatment_advice: str = Field(default="", max_length=500)


class MedicalRecordUpdate(BaseModel):
    chief_complaint: str | None = Field(default=None, min_length=1, max_length=200)
    present_illness: str | None = Field(default=None, max_length=1000)
    past_history: str | None = Field(default=None, max_length=1000)
    personal_history: str | None = Field(default=None, max_length=1000)
    marital_history: str | None = Field(default=None, max_length=1000)
    family_history: str | None = Field(default=None, max_length=1000)
    physical_exam: str | None = Field(default=None, max_length=1000)
    auxiliary_exam: str | None = Field(default=None, max_length=1000)
    treatment_advice: str | None = Field(default=None, max_length=500)


class MedicalRecordResponse(MedicalRecordCreate):
    id: int
    encounter_id: int
    written_by: str
    created_at: datetime
    updated_at: datetime | None
    signed_by: str | None
    signed_at: datetime | None
    model_config = ConfigDict(from_attributes=True)


class QualityResponse(BaseModel):
    score: int
    passed: bool
    missing_fields: list[str]


class AdverseReactionCreate(BaseModel):
    drug_name: str = ""
    reaction: str = Field(min_length=1, max_length=500)
    severity: str = Field(default="moderate", pattern="^(mild|moderate|severe)$")
    action_taken: str = ""
    pause_encounter: bool = True


class AdverseReactionResponse(AdverseReactionCreate):
    id: int
    encounter_id: int
    reported_by: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
