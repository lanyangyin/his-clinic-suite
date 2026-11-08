from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class InboundItemCreate(BaseModel):
    kind: Literal["drug", "material"] = "drug"
    drug_id: int | None = None
    material_id: int | None = None
    batch_no: str = Field(default="", max_length=30)
    expiry: date | None = None
    quantity: int = Field(gt=0)
    unit_price: float = Field(default=0, ge=0)
    insurance_code: str = Field(default="", max_length=40)
    registration_no: str = Field(default="", max_length=60)
    manufacturer: str = Field(default="", max_length=100)
    storage_condition: str = Field(default="", max_length=20)
    warehouse: str = Field(default="总库", max_length=30)
    location: str = Field(default="", max_length=20)
    note: str = Field(default="", max_length=200)


class InboundOrderCreate(BaseModel):
    order_type: Literal["drug", "device", "consumable", "office", "other"] = "drug"
    supplier_id: int | None = None
    source: Literal["purchase", "return", "donation", "transfer"] = "purchase"
    delivery_no: str = Field(default="", max_length=50)
    invoice_no: str = Field(default="", max_length=50)
    note: str = Field(default="", max_length=200)
    items: list[InboundItemCreate] = Field(min_length=1)


class CheckItem(BaseModel):
    item_id: int
    rejected_qty: int = Field(default=0, ge=0)
    reject_reason: str = Field(default="", max_length=200)


class InboundCheckRequest(BaseModel):
    items: list[CheckItem] = Field(default_factory=list)


class InboundItemResponse(BaseModel):
    id: int
    order_id: int
    kind: str
    drug_id: int | None
    material_id: int | None
    name: str
    spec: str
    unit: str
    batch_no: str
    expiry: date | None
    quantity: int
    unit_price: float
    amount: float
    insurance_code: str
    registration_no: str
    manufacturer: str
    storage_condition: str
    warehouse: str
    location: str
    rejected_qty: int
    reject_reason: str
    note: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class InboundOrderResponse(BaseModel):
    id: int
    order_no: str
    order_type: str
    supplier_id: int | None
    source: str
    status: str
    delivery_no: str
    invoice_no: str
    received_by: str
    checked_by: str
    received_at: datetime | None
    checked_at: datetime | None
    stocked_at: datetime | None
    note: str
    created_at: datetime
    items: list[InboundItemResponse]
    model_config = ConfigDict(from_attributes=True)
