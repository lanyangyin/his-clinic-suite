from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class DispenseRequest(BaseModel):
    encounter_id: int


class DispenseResponse(DispenseRequest):
    id: int
    status: str
    returned_at: datetime | None = None
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
