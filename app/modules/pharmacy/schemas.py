from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class DispenseRequest(BaseModel):
    encounter_id: int
    note: str = ""


class DispenseResponse(DispenseRequest):
    id: int
    status: str
    returned_at: datetime | None = None
    verified_by: str = ""
    verified_at: datetime | None = None
    model_config = ConfigDict(from_attributes=True)


class PharmacyCallRequest(BaseModel):
    window_no: str = Field(default="", max_length=20)
    note: str = Field(default="", max_length=200)


class PharmacyCallResponse(BaseModel):
    encounter_id: int
    queue_no: str
    status: str
    window_no: str
    called_by: str
    called_at: datetime
    note: str
    model_config = ConfigDict(from_attributes=True)


class StockInRequest(BaseModel):
    drug_id: int
    batch_no: str
    expiry: date
    location: str = ""
    quantity: int = Field(gt=0)


class StockInResponse(StockInRequest):
    id: int
    model_config = ConfigDict(from_attributes=True)


class StockResponse(BaseModel):
    id: int
    drug_id: int
    batch_no: str
    expiry: date
    location: str
    quantity: int
    model_config = ConfigDict(from_attributes=True)
