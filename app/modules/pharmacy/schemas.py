from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class DispenseRequest(BaseModel):
    encounter_id: int
    note: str = ""
    pickup_code: str = ""
    receiver_name: str = ""
    receiver_relation: str = "本人"


class DispenseResponse(DispenseRequest):
    id: int
    status: str
    returned_at: datetime | None = None
    verified_by: str = ""
    verified_at: datetime | None = None
    signature_path: str = ""
    signed_at: datetime | None = None
    model_config = ConfigDict(from_attributes=True)


class PickupVerifyResponse(BaseModel):
    encounter_id: int
    patient_name: str
    code: str
    used: bool


class PharmacyCallRequest(BaseModel):
    window_no: str = Field(default="", max_length=20)
    note: str = Field(default="", max_length=200)


class PharmacyCallResponse(BaseModel):
    encounter_id: int
    queue_no: str
    status: str
    window_no: str
    called_by: str
    called_at: datetime
    note: str
    model_config = ConfigDict(from_attributes=True)


class StockInRequest(BaseModel):
    drug_id: int
    batch_no: str
    expiry: date
    location: str = ""
    quantity: int = Field(gt=0)


class StockInResponse(StockInRequest):
    id: int
    model_config = ConfigDict(from_attributes=True)


class StockResponse(BaseModel):
    id: int
    drug_id: int
    batch_no: str
    expiry: date
    location: str
    quantity: int
    model_config = ConfigDict(from_attributes=True)


class RetailItemCreate(BaseModel):
    kind: Literal["drug", "material"]
    drug_id: int | None = None
    material_id: int | None = None
    quantity: int = Field(gt=0)
    unit_price: float | None = Field(default=None, ge=0)
    warehouse: str = Field(default="药房", max_length=30)


class RetailSaleCreate(BaseModel):
    customer_name: str = Field(default="", max_length=50)
    phone: str = Field(default="", max_length=20)
    channel: Literal["cash", "wechat", "alipay"] = "cash"
    items: list[RetailItemCreate] = Field(min_length=1)


class RetailItemResponse(BaseModel):
    id: int
    kind: str
    drug_id: int | None
    material_id: int | None
    name: str
    spec: str
    unit: str
    batch_no: str
    expiry: date | None
    warehouse: str
    quantity: int
    unit_price: float
    amount: float
    model_config = ConfigDict(from_attributes=True)


class RetailSaleResponse(BaseModel):
    id: int
    sale_no: str
    customer_name: str
    phone: str
    channel: str
    total_amount: float
    status: str
    sold_by: str
    refunded_by: str
    refunded_at: datetime | None
    created_at: datetime
    items: list[RetailItemResponse]
    model_config = ConfigDict(from_attributes=True)
