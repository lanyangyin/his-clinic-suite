from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TreatmentOrderCreate(BaseModel):
    item_id: int
    quantity: int = Field(default=1, gt=0, le=100)
    note: str = Field(default="", max_length=200)


class TreatmentOrderResponse(BaseModel):
    id: int
    encounter_id: int
    charge_item_id: int
    item_name: str
    quantity: int
    note: str
    status: str
    ordered_by: str
    ordered_at: datetime
    executed_by: str | None
    executed_at: datetime | None
    model_config = ConfigDict(from_attributes=True)
