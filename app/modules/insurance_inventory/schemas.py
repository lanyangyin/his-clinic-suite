from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class PeriodRequest(BaseModel):
    start_date: date
    end_date: date


class InventoryRecord(BaseModel):
    insurance_code: str
    drug_name: str
    spec: str
    dosage_form: str
    unit: str
    batch_no: str
    expiry: str
    warehouse: str
    direction: str
    business_type: str
    quantity: int
    unit_price: float
    amount: float
    occurred_at: str
    ref_type: str
    ref_id: int | None
    balance_after: int


class InventoryPreviewResponse(BaseModel):
    start_date: date
    end_date: date
    record_count: int
    total_amount: float
    unmatched_count: int
    records: list[InventoryRecord]


class UploadResponse(BaseModel):
    id: int
    upload_no: str
    start_date: date
    end_date: date
    record_count: int
    total_amount: float
    status: str
    channel: str = "mock"
    created_by: str
    created_at: datetime
    submitted_at: datetime | None
    model_config = ConfigDict(from_attributes=True)


class UploadDetail(UploadResponse):
    payload: str
    response: str
