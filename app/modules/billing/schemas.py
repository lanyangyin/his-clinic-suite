from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PaymentAllocationCreate(BaseModel):
    channel: str
    amount: float = Field(gt=0)


class PaymentAllocationResponse(BaseModel):
    channel: str
    amount: float
    trade_no: str = ""
    model_config = ConfigDict(from_attributes=True)


class PaymentCreate(BaseModel):
    encounter_id: int
    # 混合支付时使用；为空则走单渠道 channel
    allocations: list[PaymentAllocationCreate] = Field(default_factory=list)
    discount_amount: float = Field(default=0, ge=0)
    discount_reason: str = Field(default="", max_length=200)
    # cash / wechat / alipay / pos / insurance_card
    channel: str = "cash"
    # 微信/支付宝付款码
    auth_code: str = ""
    # POS/医保卡卡号或读卡器返回值
    card_no: str = ""


class PaymentResponse(BaseModel):
    encounter_id: int
    id: int
    amount: float
    status: str
    insurance_amount: float
    self_pay_amount: float
    # 发票票据号
    invoice_no: str | None = None
    invoice_batch_id: int | None = None
    invoice_status: str = "normal"
    invoice_print_count: int = 0
    invoice_printed_at: datetime | None = None
    invoice_voided_at: datetime | None = None
    invoice_voided_by: str = ""
    invoice_void_reason: str = ""
    channel: str = "cash"
    channel_trade_no: str = ""
    channel_status: str = "success"
    created_by: str = ""
    refunded_amount: float = 0
    refunded_insurance_amount: float = 0
    refunded_self_pay_amount: float = 0
    net_amount: float = 0
    net_self_pay_amount: float = 0
    discount_amount: float = 0
    discount_reason: str = ""
    discount_by: str = ""
    allocations: list[PaymentAllocationResponse] = Field(default_factory=list)
    model_config = ConfigDict(from_attributes=True)


class RefundItem(BaseModel):
    charge_id: int
    quantity: int = Field(gt=0)


class RefundRequest(BaseModel):
    items: list[RefundItem] = Field(min_length=1)
    reason: str = Field(default="", max_length=200)


class BillingSummary(BaseModel):
    paid_count: int
    paid_total: float
    refunded_count: int
    refunded_total: float
