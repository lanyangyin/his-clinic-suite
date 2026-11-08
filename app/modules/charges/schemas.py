from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ChargeItemCreate(BaseModel):
    code: str = Field(min_length=1, max_length=30)
    name: str = Field(min_length=1, max_length=100)
    category: str = Field(default="other", pattern="^(registration|consultation|lab|imaging|treatment|other)$")
    price: float = Field(ge=0)
    insurance_ratio: float = Field(default=0.7, ge=0, le=1)


class ChargeItemResponse(ChargeItemCreate):
    id: int
    active: bool
    model_config = ConfigDict(from_attributes=True)


class EncounterChargeResponse(BaseModel):
    id: int
    encounter_id: int
    charge_type: str
    item_name: str
    quantity: int
    unit_price: float
    amount: float
    insurance_ratio: float
    status: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ChargeSummary(BaseModel):
    encounter_id: int
    total_pending: float
    total_paid: float
    total_refunded: float
