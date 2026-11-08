from pydantic import BaseModel, ConfigDict


class PaymentCreate(BaseModel):
    encounter_id: int


class PaymentResponse(PaymentCreate):
    id: int
    amount: float
    status: str
    insurance_amount: float
    self_pay_amount: float
    # 发票票据号
    invoice_no: str | None = None
    model_config = ConfigDict(from_attributes=True)


class BillingSummary(BaseModel):
    paid_count: int
    paid_total: float
    refunded_count: int
    refunded_total: float
