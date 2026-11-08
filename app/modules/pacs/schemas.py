from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ImagingItemCreate(BaseModel):
    code: str = Field(min_length=1, max_length=20)
    name: str = Field(min_length=1, max_length=100)
    body_part: str = Field(default="", max_length=50)
    price: float = Field(default=0, ge=0)


class ImagingItemResponse(ImagingItemCreate):
    id: int
    model_config = ConfigDict(from_attributes=True)


class ImagingRequestCreate(BaseModel):
    item_id: int


class ImagingReportRequest(BaseModel):
    report: str = Field(min_length=1, max_length=500)
    image_url: str = Field(default="", max_length=200)


class ImagingRequestResponse(BaseModel):
    id: int
    encounter_id: int
    item_id: int
    item_name: str
    accession_no: str
    status: str
    requested_by: str
    requested_at: datetime
    reported_at: datetime | None
    report: str | None
    image_url: str
    model_config = ConfigDict(from_attributes=True)
