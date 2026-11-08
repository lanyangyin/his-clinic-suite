from pydantic import BaseModel, ConfigDict


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
    channel: str = "cash"
    channel_trade_no: str = ""
    channel_status: str = "success"
    model_config = ConfigDict(from_attributes=True)


class BillingSummary(BaseModel):
    paid_count: int
    paid_total: float
    refunded_count: int
    refunded_total: float
