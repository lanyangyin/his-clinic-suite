from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class StocktakeCreate(BaseModel):
    kind: str = Field(pattern="^(drug|material)$")
    warehouse: str = Field(default="总库", max_length=30)
    title: str = Field(default="", max_length=100)
    note: str = Field(default="", max_length=200)


class StocktakeItemUpdate(BaseModel):
    item_id: int
    actual_quantity: int = Field(ge=0)


class StocktakeCounts(BaseModel):
    items: list[StocktakeItemUpdate]


class StocktakeItemResponse(BaseModel):
    id: int
    kind: str
    drug_id: int | None
    material_id: int | None
    name: str
    spec: str
    batch_no: str
    warehouse: str
    book_quantity: int
    actual_quantity: int | None
    unit_price: float
    difference: int | None = None
    model_config = ConfigDict(from_attributes=True)


class StocktakeResponse(BaseModel):
    id: int
    take_no: str
    title: str
    kind: str
    warehouse: str
    status: str
    note: str
    created_by: str
    created_at: datetime
    completed_by: str
    completed_at: datetime | None
    items: list[StocktakeItemResponse] = Field(default_factory=list)
    model_config = ConfigDict(from_attributes=True)
