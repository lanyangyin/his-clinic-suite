from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class RefundExportTemplate(Base):
    """退费留痕导出字段模板。"""

    __tablename__ = "refund_export_templates"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    fields: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_by: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)


class FinancialVoucher(Base):
    """财务凭证：按收费/退费/住院缴费生成，业务键唯一防重复。"""

    __tablename__ = "financial_vouchers"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    voucher_no: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    biz_type: Mapped[str] = mapped_column(String(20), nullable=False)
    biz_id: Mapped[int] = mapped_column(nullable=False)
    amount: Mapped[float] = mapped_column(nullable=False)
    direction: Mapped[str] = mapped_column(String(10), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)


class FinancialReconciliation(Base):
    """财务日对账签收（操作人+时间，非 CA 签章）。"""

    __tablename__ = "financial_reconciliations"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    biz_date: Mapped[str] = mapped_column(String(10), unique=True, nullable=False)
    total_payment: Mapped[float] = mapped_column(nullable=False)
    total_inpatient: Mapped[float] = mapped_column(nullable=False)
    total_refund: Mapped[float] = mapped_column(nullable=False)
    net: Mapped[float] = mapped_column(nullable=False)
    operator: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    certificate_id: Mapped[int | None] = mapped_column(nullable=True)
    content_hash: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    signature: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)


class InstitutionSetting(Base):
    """机构级运行参数：医保国家接口与机构抬头。"""

    __tablename__ = "institution_settings"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    clinic_name: Mapped[str] = mapped_column(String(100), default="", nullable=False)
    clinic_address: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    clinic_phone: Mapped[str] = mapped_column(String(40), default="", nullable=False)
    insurance_enabled: Mapped[bool] = mapped_column(default=False, nullable=False)
    national_url: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    national_token: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    national_org_code: Mapped[str] = mapped_column(String(100), default="", nullable=False)
    national_region_code: Mapped[str] = mapped_column(String(100), default="", nullable=False)
    national_operator: Mapped[str] = mapped_column(String(50), default="HIS", nullable=False)
    national_org_name: Mapped[str] = mapped_column(String(100), default="", nullable=False)
    national_infver: Mapped[str] = mapped_column(String(10), default="V1.0", nullable=False)
    national_recer_sys_code: Mapped[str] = mapped_column(String(20), default="HIS", nullable=False)
    national_mdtrtarea_code: Mapped[str] = mapped_column(String(100), default="", nullable=False)
    national_insuplc_code: Mapped[str] = mapped_column(String(100), default="", nullable=False)
    national_med_type: Mapped[str] = mapped_column(String(10), default="11", nullable=False)
    national_sign_type: Mapped[str] = mapped_column(String(10), default="SM2", nullable=False)
    national_security_mode: Mapped[str] = mapped_column(String(20), default="plain", nullable=False)
    national_timeout: Mapped[int] = mapped_column(Integer, default=15, nullable=False)
    national_retry: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    national_dev_no: Mapped[str] = mapped_column(String(100), default="", nullable=False)
    national_dev_safe_info: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    national_cert_path: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    national_cert_password: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    national_sm2_private_key: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    national_sm2_public_key: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    national_sm4_key: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    national_mock: Mapped[bool] = mapped_column(default=False, nullable=False)
    updated_by: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class SystemSetting(Base):
    """可在管理台维护的运行参数（key/value）。"""

    __tablename__ = "system_settings"

    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="", nullable=False)
    updated_by: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
