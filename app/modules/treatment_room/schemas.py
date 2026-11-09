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
    treatment_order_id: int | None = None
    procedure_name: str = Field(min_length=1, max_length=100)
    diagnosis: str = Field(default="", max_length=200)
    priority: str = Field(default="routine", pattern="^(routine|urgent)$")
    charge_item_id: int | None = None
    price: float = Field(default=0, ge=0)
    note: str = Field(default="", max_length=200)


class StartRequest(BaseModel):
    consent: bool
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
    diagnosis: str
    status: str
    priority: str
    price: float
    consent: bool
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
