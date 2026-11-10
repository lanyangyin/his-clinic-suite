from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class InvoiceBatchCreate(BaseModel):
    prefix: str = Field(default="INV", min_length=1, max_length=20)
    start_no: int = Field(ge=1)
    end_no: int = Field(ge=1)
    assigned_to: str = Field(default="", max_length=50)
    note: str = Field(default="", max_length=200)


class InvoiceBatchResponse(BaseModel):
    id: int
    prefix: str
    start_no: int
    end_no: int
    next_no: int
    assigned_to: str
    status: str
    note: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
