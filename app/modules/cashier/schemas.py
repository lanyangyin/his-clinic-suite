from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ShiftOpen(BaseModel):
    opening_float: float = Field(default=0, ge=0)
    note: str = Field(default="", max_length=200)


class ShiftClose(BaseModel):
    counted_cash: float = Field(ge=0)
    note: str = Field(default="", max_length=200)


class ShiftResponse(BaseModel):
    id: int
    shift_no: str
    cashier: str
    opened_at: datetime
    closed_at: datetime | None
    opening_float: float
    counted_cash: float | None
    expected_cash: float | None
    difference: float | None
    status: str
    note: str
    model_config = ConfigDict(from_attributes=True)
