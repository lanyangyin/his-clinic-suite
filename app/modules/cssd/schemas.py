from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class SetCreate(BaseModel):
    code: str = Field(min_length=1, max_length=30)
    name: str = Field(min_length=1, max_length=100)
    department: str = Field(default="", max_length=50)
    note: str = Field(default="", max_length=200)


class SetResponse(SetCreate):
    id: int
    active: bool
    model_config = ConfigDict(from_attributes=True)


class BatchCreate(BaseModel):
    batch_no: str | None = Field(default=None, max_length=30)
    sterilizer: str = Field(min_length=1, max_length=50)
    method: str = Field(default="steam", pattern="^(steam|plasma|chemical)$")
    cycle: str = Field(default="", max_length=30)
    temperature: float | None = Field(default=None, ge=0, le=300)
    pressure: float | None = Field(default=None, ge=0, le=1000)
    duration_min: int | None = Field(default=None, ge=0, le=1000)
    operator: str = Field(default="", max_length=50)
    chemical_indicator: str = Field(default="pending", pattern="^(pending|pass|fail)$")
    biological_indicator: str = Field(default="pending", pattern="^(pending|pass|fail)$")
    note: str = Field(default="", max_length=200)


class BatchResponse(BaseModel):
    id: int
    batch_no: str
    sterilizer: str
    method: str
    cycle: str
    temperature: float | None
    pressure: float | None
    duration_min: int | None
    started_at: datetime
    ended_at: datetime | None
    operator: str
    chemical_indicator: str
    biological_indicator: str
    release_status: str
    released_by: str
    released_at: datetime | None
    note: str
    model_config = ConfigDict(from_attributes=True)


class ReleaseRequest(BaseModel):
    released_by: str = Field(default="", max_length=50)


class RejectRequest(BaseModel):
    reason: str = Field(default="", max_length=200)


class PackageCreate(BaseModel):
    package_code: str = Field(min_length=1, max_length=50)
    set_id: int
    batch_id: int
    expiry: date
    location: str = Field(default="", max_length=50)
    note: str = Field(default="", max_length=200)


class PackageResponse(BaseModel):
    id: int
    package_code: str
    set_id: int
    set_name: str
    batch_id: int
    batch_no: str
    sterilized_at: datetime
    expiry: date
    status: str
    location: str
    note: str
    model_config = ConfigDict(from_attributes=True)


class IssueRequest(BaseModel):
    department: str = Field(min_length=1, max_length=50)
    note: str = Field(default="", max_length=200)


class UseRequest(BaseModel):
    department: str = Field(min_length=1, max_length=50)
    patient_id: int | None = None
    encounter_id: int | None = None
    note: str = Field(default="", max_length=200)


class UsageResponse(BaseModel):
    id: int
    package_id: int
    department: str
    patient_id: int | None
    encounter_id: int | None
    used_at: datetime
    used_by: str
    note: str
    model_config = ConfigDict(from_attributes=True)


class PackageRecallRequest(BaseModel):
    reason: str = Field(default="", max_length=200)
