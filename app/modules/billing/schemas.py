from pydantic import BaseModel, ConfigDict, Field


class PaymentCreate(BaseModel):
    encounter_id: int
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
    channel: str = "cash"
    channel_trade_no: str = ""
    channel_status: str = "success"
    created_by: str = ""
    refunded_amount: float = 0
    refunded_insurance_amount: float = 0
    refunded_self_pay_amount: float = 0
    net_amount: float = 0
    net_self_pay_amount: float = 0
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
