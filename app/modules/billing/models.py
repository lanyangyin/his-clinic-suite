from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    # MVP：一次就诊只允许一笔收费
    encounter_id: Mapped[int] = mapped_column(
        ForeignKey("encounters.id"), unique=True, nullable=False, index=True
    )
    amount: Mapped[float] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="paid", nullable=False)
    # 医保支付金额（医保服务不可用时降级为 0，全额自费）
    insurance_amount: Mapped[float] = mapped_column(
        nullable=False, default=0.0, server_default="0"
    )
    # 发票票据号（收费时生成）
    invoice_no: Mapped[str | None] = mapped_column(String(30), nullable=True)
    invoice_batch_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, nullable=False
    )
    # cash / wechat / alipay / pos / insurance_card
    channel: Mapped[str] = mapped_column(
        String(20), default="cash", server_default="cash", nullable=False
    )
    channel_trade_no: Mapped[str] = mapped_column(
        String(64), default="", server_default="", nullable=False
    )
    # success / mock
    channel_status: Mapped[str] = mapped_column(
        String(20), default="success", server_default="success", nullable=False
    )
    created_by: Mapped[str] = mapped_column(
        String(50), default="", server_default="", nullable=False
    )
    # 已退金额累计（支持部分退费）
    refunded_amount: Mapped[float] = mapped_column(
        default=0.0, server_default="0", nullable=False
    )
    refunded_insurance_amount: Mapped[float] = mapped_column(
        default=0.0, server_default="0", nullable=False
    )

    @property
    def self_pay_amount(self) -> float:
        """原始自费金额 = 总金额 - 医保支付金额。"""
        return round(self.amount - self.insurance_amount, 2)

    @property
    def refunded_self_pay_amount(self) -> float:
        return round(self.refunded_amount - self.refunded_insurance_amount, 2)

    @property
    def net_amount(self) -> float:
        """扣除已退后的净收费金额。"""
        return round(self.amount - self.refunded_amount, 2)

    @property
    def net_self_pay_amount(self) -> float:
        return round(self.self_pay_amount - self.refunded_self_pay_amount, 2)


class ChargeRefund(Base):
    """按费用明细的退费记录（可只退 1 颗药）。"""

    __tablename__ = "charge_refunds"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    payment_id: Mapped[int] = mapped_column(
        ForeignKey("payments.id"), nullable=False, index=True
    )
    charge_id: Mapped[int] = mapped_column(
        ForeignKey("encounter_charges.id"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(nullable=False)
    amount: Mapped[float] = mapped_column(nullable=False)
    insurance_amount: Mapped[float] = mapped_column(nullable=False)
    self_pay_amount: Mapped[float] = mapped_column(nullable=False)
    refund_no: Mapped[str] = mapped_column(String(40), nullable=False)
    channel: Mapped[str] = mapped_column(
        String(20), default="cash", server_default="cash", nullable=False
    )
    channel_trade_no: Mapped[str] = mapped_column(
        String(64), default="", server_default="", nullable=False
    )
    operator: Mapped[str] = mapped_column(
        String(50), default="", server_default="", nullable=False
    )
    reason: Mapped[str] = mapped_column(
        String(200), default="", server_default="", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, nullable=False
    )
