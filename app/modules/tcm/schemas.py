from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class HerbCreate(BaseModel):
    code: str = Field(min_length=1, max_length=30)
    name: str = Field(min_length=1, max_length=100)
    spec: str = Field(default="", max_length=60)
    unit: str = Field(default="g", max_length=10)
    price_per_g: float = Field(default=0, ge=0)
    insurance_code: str = Field(default="", max_length=40)
    toxicity: str = Field(default="none", pattern="^(none|toxic|precious)$")
    note: str = Field(default="", max_length=200)


class HerbResponse(HerbCreate):
    id: int
    active: bool
    model_config = ConfigDict(from_attributes=True)


class PrescriptionItemCreate(BaseModel):
    herb_id: int
    dose_g: float = Field(gt=0, le=1000)
    special: str = Field(default="none", pattern="^(none|first|last|wrap|separate|melt|infuse)$")
    note: str = Field(default="", max_length=100)


class PrescriptionCreate(BaseModel):
    formula_name: str = Field(default="", max_length=100)
    usage: str = Field(default="internal", pattern="^(internal|external)$")
    packs: int = Field(default=1, ge=1, le=100)
    decoct_service: str = Field(default="decoct", pattern="^(decoct|self)$")
    decoction_method: str = Field(default="常规煎煮", max_length=50)
    note: str = Field(default="", max_length=200)
    items: list[PrescriptionItemCreate] = Field(min_length=1)


class PrescriptionItemResponse(BaseModel):
    id: int
    herb_id: int
    herb_name: str
    dose_g: float
    special: str
    note: str
    model_config = ConfigDict(from_attributes=True)


class PrescriptionResponse(BaseModel):
    id: int
    prescription_no: str
    encounter_id: int
    doctor: str
    formula_name: str
    usage: str
    packs: int
    decoct_service: str
    decoction_method: str
    status: str
    total_amount: float
    review_by: str
    reviewed_at: datetime | None
    dispense_by: str
    dispensed_at: datetime | None
    note: str
    created_at: datetime
    items: list[PrescriptionItemResponse]
    model_config = ConfigDict(from_attributes=True)


class SoakRequest(BaseModel):
    soak_minutes: int = Field(default=30, ge=0, le=240)
    note: str = Field(default="", max_length=200)


class DecoctRequest(BaseModel):
    machine_no: str = Field(min_length=1, max_length=30)
    decoct_minutes: int = Field(default=40, ge=1, le=300)
    note: str = Field(default="", max_length=200)


class PackageRequest(BaseModel):
    bags: int = Field(gt=0, le=200)
    bag_volume_ml: int | None = Field(default=None, ge=0, le=1000)
    expires_days: int = Field(default=7, ge=1, le=30)
    note: str = Field(default="", max_length=200)


class IssueRequest(BaseModel):
    pickup_method: str = Field(default="self", pattern="^(self|delivery)$")
    receiver: str = Field(min_length=1, max_length=50)
    note: str = Field(default="", max_length=200)


class BagResponse(BaseModel):
    id: int
    bag_no: str
    expiry: datetime | None
    label: str
    model_config = ConfigDict(from_attributes=True)


class DecoctionResponse(BaseModel):
    id: int
    order_no: str
    prescription_id: int
    encounter_id: int
    patient_name: str
    status: str
    soak_minutes: int | None
    decoct_minutes: int | None
    machine_no: str
    operator: str
    bags: int
    bag_volume_ml: int | None
    received_at: datetime
    soaked_at: datetime | None
    decocted_at: datetime | None
    packaged_at: datetime | None
    completed_at: datetime | None
    expires_at: datetime | None
    pickup_method: str
    receiver: str
    issued_at: datetime | None
    note: str
    bags_list: list[BagResponse] = Field(default_factory=list)
    model_config = ConfigDict(from_attributes=True)
