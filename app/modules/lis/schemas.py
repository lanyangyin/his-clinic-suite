from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class LabItemCreate(BaseModel):
    code: str = Field(min_length=1, max_length=20)
    name: str = Field(min_length=1, max_length=100)
    price: float = Field(default=0, ge=0)


class LabItemResponse(LabItemCreate):
    id: int
    model_config = ConfigDict(from_attributes=True)


class LabRequestCreate(BaseModel):
    item_id: int


class LabReportRequest(BaseModel):
    result: str = Field(min_length=1, max_length=500)


class LabRequestResponse(BaseModel):
    id: int
    encounter_id: int
    item_id: int
    item_name: str
    status: str
    requested_by: str
    requested_at: datetime
    reported_at: datetime | None
    result: str | None
    model_config = ConfigDict(from_attributes=True)
