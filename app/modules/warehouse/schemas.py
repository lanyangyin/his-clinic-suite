from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class PurchaseCreate(BaseModel):
    drug_id: int
    batch_no: str = Field(min_length=1, max_length=30)
    expiry: date
    quantity: int = Field(gt=0)
    supplier_id: int | None = None


class WarehouseStockResponse(BaseModel):
    id: int
    drug_id: int
    drug_name: str
    batch_no: str
    expiry: date
    quantity: int
    model_config = ConfigDict(from_attributes=True)


class TransferCreate(BaseModel):
    drug_id: int
    batch_no: str = Field(min_length=1, max_length=30)
    quantity: int = Field(gt=0)


class TransferResponse(BaseModel):
    drug_id: int
    batch_no: str
    transferred_quantity: int
    warehouse_quantity: int
    pharmacy_stock_id: int
    pharmacy_quantity: int


class CheckCreate(BaseModel):
    drug_id: int
    batch_no: str = Field(min_length=1, max_length=30)
    actual_quantity: int = Field(ge=0)


class CheckResponse(BaseModel):
    id: int
    drug_id: int
    batch_no: str
    expected_quantity: int
    actual_quantity: int
    diff: int
    checked_at: datetime
    checked_by: str
    model_config = ConfigDict(from_attributes=True)


class PurchaseRecordResponse(BaseModel):
    id: int
    drug_id: int
    drug_name: str
    batch_no: str
    quantity: int
    supplier_id: int | None
    supplier_name: str
    purchased_at: datetime
    purchased_by: str
    model_config = ConfigDict(from_attributes=True)
