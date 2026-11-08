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


# ---------- 出库单 ----------
class OutboundItemCreate(BaseModel):
    kind: str = Field(default="drug", pattern="^(drug|material)$")
    drug_id: int | None = None
    material_id: int | None = None
    batch_no: str = Field(default="", max_length=30)
    expiry: date | None = None
    quantity: int = Field(gt=0)
    unit_price: float = Field(default=0, ge=0)


class OutboundOrderCreate(BaseModel):
    outbound_type: str = Field(default="requisition", pattern="^(requisition|transfer|scrap|return)$")
    target_type: str = Field(default="pharmacy", pattern="^(pharmacy|department)$")
    target_name: str = Field(default="药房", max_length=50)
    note: str = Field(default="", max_length=200)
    items: list[OutboundItemCreate] = Field(min_length=1)


class OutboundItemResponse(BaseModel):
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
    issued_quantity: int
    unit_price: float
    amount: float
    insurance_code: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class OutboundOrderResponse(BaseModel):
    id: int
    outbound_no: str
    outbound_type: str
    target_type: str
    target_name: str
    applicant: str
    approver: str
    issuer: str
    status: str
    note: str
    created_at: datetime
    approved_at: datetime | None
    issued_at: datetime | None
    items: list[OutboundItemResponse]
    model_config = ConfigDict(from_attributes=True)


class OutboundIssueItem(BaseModel):
    item_id: int
    quantity: int = Field(gt=0)


class OutboundIssueRequest(BaseModel):
    items: list[OutboundIssueItem] = Field(default_factory=list)


class StockAdjustmentResponse(BaseModel):
    id: int
    adjust_no: str
    kind: str
    drug_id: int | None
    material_id: int | None
    name: str
    batch_no: str
    expected_quantity: int
    actual_quantity: int
    diff: int
    direction: str
    quantity: int
    operator: str
    note: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
