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
