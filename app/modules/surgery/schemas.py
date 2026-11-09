from datetime import datetime

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
    procedure_name: str = Field(min_length=1, max_length=100)
    diagnosis: str = Field(default="", max_length=200)
    surgeon: str = Field(default="", max_length=50)
    anesthesia_type: str = Field(default="", max_length=30)
    scheduled_at: datetime | None = None
    charge_item_id: int | None = None
    price: float = Field(default=0, ge=0)
    notes: str = Field(default="", max_length=200)


class CaseResponse(BaseModel):
    id: int
    surgery_no: str
    patient_id: int
    patient_name: str
    encounter_id: int | None
    room_id: int | None
    procedure_name: str
    diagnosis: str
    surgeon: str
    anesthesia_type: str
    scheduled_at: datetime
    status: str
    notes: str
    price: float
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    model_config = ConfigDict(from_attributes=True)


class SafetyCreate(BaseModel):
    phase: str = Field(pattern="^(sign_in|time_out|sign_out)$")
    checklist: str = Field(default="", max_length=500)


class SafetyResponse(BaseModel):
    id: int
    case_id: int
    phase: str
    checklist: str
    completed_by: str
    completed_at: datetime
    model_config = ConfigDict(from_attributes=True)


class RecordCreate(BaseModel):
    findings: str = Field(default="", max_length=500)
    procedure_detail: str = Field(default="", max_length=1000)
    implants: str = Field(default="", max_length=200)
    specimens: str = Field(default="", max_length=200)
    blood_loss_ml: int | None = Field(default=None, ge=0, le=100000)
    notes: str = Field(default="", max_length=500)


class RecordResponse(RecordCreate):
    id: int
    case_id: int
    recorded_by: str
    recorded_at: datetime
    model_config = ConfigDict(from_attributes=True)


class CountCreate(BaseModel):
    phase: str = Field(pattern="^(before|after)$")
    item_name: str = Field(min_length=1, max_length=100)
    expected: int = Field(ge=0)
    actual: int = Field(ge=0)


class CountResponse(BaseModel):
    id: int
    case_id: int
    phase: str
    item_name: str
    expected: int
    actual: int
    matched: bool
    counted_by: str
    counted_at: datetime
    model_config = ConfigDict(from_attributes=True)


class RecoveryCreate(BaseModel):
    vitals: str = Field(default="", max_length=200)
    score: int | None = Field(default=None, ge=0, le=10)
    note: str = Field(default="", max_length=500)


class RecoveryResponse(BaseModel):
    id: int
    case_id: int
    pacu_in: datetime | None
    pacu_out: datetime | None
    vitals: str
    score: int | None
    nurse: str
    note: str
    model_config = ConfigDict(from_attributes=True)

class PreopCreate(BaseModel):
    anesthesiologist: str = Field(default="", max_length=50)
    asa_grade: str = Field(default="", max_length=5)
    airway: str = Field(default="", max_length=100)
    allergies: str = Field(default="", max_length=200)
    comorbidities: str = Field(default="", max_length=300)
    fasting: str = Field(default="", max_length=100)
    consent: bool = False
    assessment: str = Field(default="", max_length=1000)
    plan: str = Field(default="", max_length=500)
    risk: str = Field(default="low", pattern="^(low|medium|high)$")


class PreopResponse(PreopCreate):
    id: int
    case_id: int
    assessed_by: str
    assessed_at: datetime
    model_config = ConfigDict(from_attributes=True)


class AnesthesiaCreate(BaseModel):
    anesthesia_type: str = Field(default="", max_length=30)
    anesthesiologist: str = Field(default="", max_length=50)
    airway: str = Field(default="", max_length=100)
    agents: str = Field(default="", max_length=500)
    monitors: str = Field(default="", max_length=200)
    vitals: str = Field(default="", max_length=500)
    fluids_ml: int | None = Field(default=None, ge=0)
    blood_loss_ml: int | None = Field(default=None, ge=0)
    urine_ml: int | None = Field(default=None, ge=0)
    complications: str = Field(default="", max_length=200)
    notes: str = Field(default="", max_length=500)


class AnesthesiaResponse(AnesthesiaCreate):
    id: int
    case_id: int
    started_at: datetime | None
    ended_at: datetime | None
    recorded_by: str
    recorded_at: datetime
    model_config = ConfigDict(from_attributes=True)
