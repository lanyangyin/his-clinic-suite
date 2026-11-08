from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class InsuranceInterfaceConfig(Base):
    """医保接口配置（单行 id=1）：实际部署时在管理台填写。

    字段留空表示未配置，进销存上传自动走 Mock；配置后走真实 HTTPS 接口。
    """

    __tablename__ = "insurance_interface_config"

    id: Mapped[int] = mapped_column(primary_key=True)
    enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="0", nullable=False
    )
    base_url: Mapped[str] = mapped_column(
        String(200), default="", server_default="", nullable=False
    )
    upload_path: Mapped[str] = mapped_column(
        String(100), default="/api/inventory/upload",
        server_default="/api/inventory/upload", nullable=False,
    )
    org_code: Mapped[str] = mapped_column(
        String(50), default="", server_default="", nullable=False
    )
    org_name: Mapped[str] = mapped_column(
        String(100), default="", server_default="", nullable=False
    )
    app_id: Mapped[str] = mapped_column(
        String(64), default="", server_default="", nullable=False
    )
    app_secret: Mapped[str] = mapped_column(
        String(128), default="", server_default="", nullable=False
    )
    sign_type: Mapped[str] = mapped_column(
        String(20), default="NONE", server_default="NONE", nullable=False
    )
    private_key: Mapped[str] = mapped_column(
        Text, default="", server_default="", nullable=False
    )
    public_key: Mapped[str] = mapped_column(
        Text, default="", server_default="", nullable=False
    )
    timeout: Mapped[int] = mapped_column(
        default=30, server_default="30", nullable=False
    )
    remark: Mapped[str] = mapped_column(
        String(200), default="", server_default="", nullable=False
    )
    updated_by: Mapped[str] = mapped_column(
        String(50), default="", server_default="", nullable=False
    )
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
