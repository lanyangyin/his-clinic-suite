from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class MaterialItemCreate(BaseModel):
    code: str = Field(min_length=1, max_length=30)
    name: str = Field(min_length=1, max_length=100)
    spec: str = Field(default="", max_length=50)
    unit: str = Field(default="", max_length=20)
    price: float = Field(default=0, ge=0)
    is_high_value: bool = False
    # consumable 耗材 / device 医疗器械 / office 办公用品 / other
    category: str = Field(default="consumable", pattern="^(consumable|device|office|other)$")
    manufacturer: str = Field(default="", max_length=100)
    registration_no: str = Field(default="", max_length=60)
    insurance_code: str = Field(default="", max_length=60)


class MaterialItemResponse(MaterialItemCreate):
    id: int
    model_config = ConfigDict(from_attributes=True)


class StockInCreate(BaseModel):
    item_id: int
    warehouse: str = Field(min_length=1, max_length=30)
    quantity: int = Field(gt=0)


class MaterialStockResponse(BaseModel):
    id: int
    item_id: int
    item_name: str
    warehouse: str
    quantity: int
    model_config = ConfigDict(from_attributes=True)


class UsageCreate(BaseModel):
    item_id: int
    serial_no: str = Field(min_length=1, max_length=50)
    encounter_id: int
    warehouse: str = Field(min_length=1, max_length=30)


class UsageResponse(BaseModel):
    id: int
    item_id: int
    item_name: str
    serial_no: str
    encounter_id: int
    warehouse: str
    used_at: datetime
    used_by: str
    model_config = ConfigDict(from_attributes=True)
