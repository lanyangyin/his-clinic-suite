from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class RoomCreate(BaseModel):
    code: str = Field(min_length=1, max_length=20)
    name: str = Field(min_length=1, max_length=50)
    location: str = Field(default="", max_length=100)


class RoomResponse(RoomCreate):
    id: int
    active: bool
    model_config = ConfigDict(from_attributes=True)


class CaseCreate(BaseModel):
    patient_id: int
    encounter_id: int | None = None
    room_id: int | None = None
    treatment_order_id: int | None = None
    procedure_name: str = Field(min_length=1, max_length=100)
    template_code: str = Field(default="", max_length=30)
    template_data: dict[str, str] = Field(default_factory=dict)
    diagnosis: str = Field(default="", max_length=200)
    priority: str = Field(default="routine", pattern="^(routine|urgent)$")
    charge_item_id: int | None = None
    price: float = Field(default=0, ge=0)
    note: str = Field(default="", max_length=200)


class StartRequest(BaseModel):
    consent: bool
    consent_version: str = Field(default="v1", max_length=20)
    consent_signer: str = Field(default="", max_length=50)
    consent_relation: str = Field(default="", max_length=20)
    consent_signature_path: str = Field(default="", max_length=200)
    anesthesia: str = Field(default="", max_length=100)
    findings: str = Field(default="", max_length=500)


class CompleteRequest(BaseModel):
    findings: str = Field(default="", max_length=500)
    procedure_detail: str = Field(min_length=1, max_length=1000)
    sutures: str = Field(default="", max_length=100)
    dressing: str = Field(default="", max_length=200)
    materials: str = Field(default="", max_length=200)
    complications: str = Field(default="", max_length=200)
    note: str = Field(default="", max_length=200)


class CaseResponse(BaseModel):
    id: int
    case_no: str
    patient_id: int
    patient_name: str
    encounter_id: int | None
    room_id: int | None
    room_name: str
    procedure_name: str
    template_code: str
    template_data: str
    diagnosis: str
    status: str
    priority: str
    charge_item_id: int | None
    price: float
    consent: bool
    consent_version: str
    consent_signer: str
    consent_relation: str
    consent_signature_path: str
    consent_signed_at: datetime | None
    kit_applied: bool
    anesthesia: str
    findings: str
    procedure_detail: str
    sutures: str
    dressing: str
    materials: str
    complications: str
    operator: str
    requested_by: str
    started_at: datetime | None
    completed_at: datetime | None
    note: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class TreatmentTemplate(BaseModel):
    code: str
    name: str
    fields: list[dict]
    configured: bool = False
    charge_item_id: int | None = None
    charge_item_name: str = ""
    price: float = 0
    material_id: int | None = None
    material_name: str = ""
    material_quantity: int = 1
    warehouse: str = "总库"
    materials: list[dict] = Field(default_factory=list)

class FollowUpCreate(BaseModel):
    case_id: int | None = None
    patient_id: int
    encounter_id: int | None = None
    due_date: date
    purpose: str = Field(default="换药", max_length=50)
    note: str = Field(default="", max_length=200)


class FollowUpResponse(BaseModel):
    id: int
    case_id: int | None
    patient_id: int
    patient_name: str
    encounter_id: int | None
    due_date: date
    purpose: str
    status: str
    note: str
    result_note: str
    healing_score: int | None
    photo_path: str
    completed_by: str
    created_at: datetime
    completed_at: datetime | None
    model_config = ConfigDict(from_attributes=True)

class TemplateConfigUpdate(BaseModel):
    charge_item_id: int | None = None
    price: float = Field(default=0, ge=0)
    material_id: int | None = None
    material_quantity: int = Field(default=1, ge=0, le=10000)
    warehouse: str = Field(default="总库", max_length=30)
    materials: list["TemplateMaterialUpdate"] = Field(default_factory=list)
    active: bool = True


class TemplateConfigResponse(BaseModel):
    template_code: str
    charge_item_id: int | None
    charge_item_name: str
    price: float
    material_id: int | None
    material_name: str
    material_quantity: int
    warehouse: str
    active: bool
    model_config = ConfigDict(from_attributes=True)

class TemplateMaterialUpdate(BaseModel):
    material_id: int
    quantity: int = Field(default=1, ge=1, le=10000)
    warehouse: str = Field(default="总库", max_length=30)


TemplateConfigUpdate.model_rebuild()

class FollowUpComplete(BaseModel):
    result_note: str = Field(default="", max_length=500)
    healing_score: int | None = Field(default=None, ge=0, le=10)
    next_due_date: date | None = None
    next_purpose: str = Field(default="换药", max_length=50)

