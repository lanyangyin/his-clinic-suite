from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ProcedureMaterialCreate(BaseModel):
    material_id: int
    quantity: int = Field(default=1, gt=0, le=10000)
    warehouse: str = Field(default="总库", max_length=30)


class ProcedureMaterialResponse(BaseModel):
    id: int
    source_type: str
    source_id: int
    name: str
    quantity: int
    unit_price: float
    amount: float
    warehouse: str
    operator: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
