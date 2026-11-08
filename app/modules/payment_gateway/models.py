from datetime import datetime

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class PaymentChannelConfig(Base):
    """支付通道配置：默认全空，未配置时收费走模拟；实际部署再填。"""

    __tablename__ = "payment_channel_configs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    # cash / wechat / alipay / pos / insurance_card
    channel: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="0", nullable=False
    )
    display_name: Mapped[str] = mapped_column(
        String(50), default="", server_default="", nullable=False
    )
    gateway_url: Mapped[str] = mapped_column(
        String(200), default="", server_default="", nullable=False
    )
    merchant_id: Mapped[str] = mapped_column(
        String(64), default="", server_default="", nullable=False
    )
    app_id: Mapped[str] = mapped_column(
        String(64), default="", server_default="", nullable=False
    )
    api_secret: Mapped[str] = mapped_column(
        String(128), default="", server_default="", nullable=False
    )
    # POS 终端号 / 医保读卡器终端号
    terminal_id: Mapped[str] = mapped_column(
        String(64), default="", server_default="", nullable=False
    )
    cert_path: Mapped[str] = mapped_column(
        String(200), default="", server_default="", nullable=False
    )
    remark: Mapped[str] = mapped_column(
        String(200), default="", server_default="", nullable=False
    )
    updated_by: Mapped[str] = mapped_column(
        String(50), default="", server_default="", nullable=False
    )
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
