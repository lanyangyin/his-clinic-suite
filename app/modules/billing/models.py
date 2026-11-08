from datetime import datetime

from sqlalchemy import DateTime, String, ForeignKey
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
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, nullable=False
    )

    @property
    def self_pay_amount(self) -> float:
        """自费金额 = 总金额 - 医保支付金额。"""
        return round(self.amount - self.insurance_amount, 2)
