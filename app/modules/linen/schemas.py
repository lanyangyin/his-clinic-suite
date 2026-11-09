from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class LinenBatchCreate(BaseModel):
    batch_no: str | None = Field(default=None, max_length=30)
    category: str = Field(default="bedding", pattern="^(bedding|uniform|curtain|other)$")
    item_name: str = Field(min_length=1, max_length=100)
    quantity: int = Field(gt=0)
    unit: str = Field(default="件", max_length=20)
    source_department: str = Field(default="", max_length=50)
    soil_level: str = Field(default="normal", pattern="^(normal|contaminated|infectious)$")
    wash_method: str = Field(default="thermal", pattern="^(thermal|chemical)$")
    temperature: float | None = Field(default=None, ge=0, le=200)
    duration_min: int | None = Field(default=None, ge=0, le=1000)
    detergent: str = Field(default="", max_length=100)
    operator: str = Field(default="", max_length=50)
    washed_at: datetime | None = None
    note: str = Field(default="", max_length=200)


class LinenBatchResponse(BaseModel):
    id: int
    batch_no: str
    category: str
    item_name: str
    quantity: int
    unit: str
    source_department: str
    soil_level: str
    wash_method: str
    temperature: float | None
    duration_min: int | None
    detergent: str
    washed_at: datetime
    operator: str
    status: str
    note: str
    distributed_quantity: int
    remaining_quantity: int
    model_config = ConfigDict(from_attributes=True)


class DistributionCreate(BaseModel):
    department: str = Field(min_length=1, max_length=50)
    quantity: int = Field(gt=0)
    note: str = Field(default="", max_length=200)


class DistributionResponse(BaseModel):
    id: int
    batch_id: int
    department: str
    quantity: int
    distributed_at: datetime
    distributed_by: str
    note: str
    model_config = ConfigDict(from_attributes=True)


class RecallCreate(BaseModel):
    reason: str = Field(default="", max_length=200)


class CurtainCreate(BaseModel):
    department: str = Field(min_length=1, max_length=50)
    room: str = Field(default="", max_length=50)
    curtain_no: str = Field(min_length=1, max_length=50)
    event: str = Field(pattern="^(remove|wash|reinstall)$")
    event_at: datetime | None = None
    method: str = Field(default="", max_length=50)
    operator: str = Field(default="", max_length=50)
    next_due: date | None = None
    note: str = Field(default="", max_length=200)


class CurtainResponse(BaseModel):
    id: int
    department: str
    room: str
    curtain_no: str
    event: str
    event_at: datetime
    method: str
    operator: str
    next_due: date | None
    note: str
    model_config = ConfigDict(from_attributes=True)


class LinenSummary(BaseModel):
    start_date: date
    end_date: date
    batch_count: int
    total_quantity: int
    distributed_quantity: int
    recalled_count: int
    by_category: dict[str, int]
