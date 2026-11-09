from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class AcceptanceItemCreate(BaseModel):
    kind: str = Field(default="drug", pattern="^(drug|material)$")
    name: str = Field(min_length=1, max_length=100)
    spec: str = Field(default="", max_length=60)
    batch_no: str = Field(default="", max_length=30)
    expiry: date | None = None
    quantity: int = Field(default=0, ge=0)
    manufacturer: str = Field(default="", max_length=100)
    approval_no: str = Field(default="", max_length=60)
    result: str = Field(default="qualified", pattern="^(qualified|unqualified)$")
    note: str = Field(default="", max_length=200)


class AcceptanceCreate(BaseModel):
    supplier_id: int | None = None
    supplier_name: str = Field(default="", max_length=100)
    delivery_no: str = Field(default="", max_length=50)
    transport_temp: float | None = Field(default=None, ge=-50, le=100)
    transport_ok: bool = True
    result: str = Field(default="qualified", pattern="^(qualified|unqualified)$")
    note: str = Field(default="", max_length=200)
    items: list[AcceptanceItemCreate] = Field(min_length=1)


class AcceptanceItemResponse(BaseModel):
    id: int
    kind: str
    name: str
    spec: str
    batch_no: str
    expiry: date | None
    quantity: int
    result: str
    model_config = ConfigDict(from_attributes=True)


class AcceptanceResponse(BaseModel):
    id: int
    acceptance_no: str
    supplier_name: str
    delivery_no: str
    arrival_at: datetime
    transport_temp: float | None
    transport_ok: bool
    result: str
    accepted_by: str
    note: str
    items: list[AcceptanceItemResponse]
    model_config = ConfigDict(from_attributes=True)


class StorageLogCreate(BaseModel):
    log_type: str = Field(default="temperature", pattern="^(temperature|maintenance|display)$")
    area: str = Field(default="药房", max_length=50)
    temperature: float | None = Field(default=None, ge=-50, le=100)
    humidity: float | None = Field(default=None, ge=0, le=100)
    equipment: str = Field(default="", max_length=50)
    note: str = Field(default="", max_length=200)


class StorageLogResponse(BaseModel):
    id: int
    log_type: str
    area: str
    temperature: float | None
    humidity: float | None
    equipment: str
    result: str
    operator: str
    note: str
    recorded_at: datetime
    model_config = ConfigDict(from_attributes=True)


class AdverseCreate(BaseModel):
    patient_name: str = Field(min_length=1, max_length=50)
    drug_name: str = Field(min_length=1, max_length=100)
    batch_no: str = Field(default="", max_length=30)
    reaction: str = Field(min_length=1, max_length=200)
    severity: str = Field(default="mild", pattern="^(mild|moderate|severe)$")


class AdverseResponse(BaseModel):
    id: int
    patient_name: str
    drug_name: str
    batch_no: str
    reaction: str
    severity: str
    reported_by: str
    reported_at: datetime
    status: str
    model_config = ConfigDict(from_attributes=True)


class RecallCreate(BaseModel):
    drug_name: str = Field(min_length=1, max_length=100)
    batch_no: str = Field(default="", max_length=30)
    reason: str = Field(min_length=1, max_length=200)
    level: str = Field(default="3", pattern="^(1|2|3)$")
    note: str = Field(default="", max_length=200)


class RecallResponse(BaseModel):
    id: int
    recall_no: str
    drug_name: str
    batch_no: str
    reason: str
    level: str
    status: str
    initiated_at: datetime
    completed_at: datetime | None
    operator: str
    note: str
    model_config = ConfigDict(from_attributes=True)


class PersonnelCreate(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    role: str = Field(default="", max_length=50)
    certificate_no: str = Field(default="", max_length=60)
    valid_until: date | None = None
    training_date: date | None = None
    note: str = Field(default="", max_length=200)


class PersonnelResponse(BaseModel):
    id: int
    name: str
    role: str
    certificate_no: str
    valid_until: date | None
    training_date: date | None
    status: str
    note: str
    model_config = ConfigDict(from_attributes=True)
