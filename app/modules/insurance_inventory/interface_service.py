"""医保接口配置读写（单行；未配置=Mock）。"""
from datetime import datetime

from sqlalchemy.orm import Session

from .interface_models import InsuranceInterfaceConfig


def get_config(db: Session) -> InsuranceInterfaceConfig | None:
    return db.get(InsuranceInterfaceConfig, 1)


def is_configured(config: InsuranceInterfaceConfig | None) -> bool:
    return bool(
        config
        and config.enabled
        and config.base_url.strip()
        and config.org_code.strip()
    )


def save_config(
    db: Session,
    *,
    enabled: bool,
    base_url: str,
    upload_path: str,
    org_code: str,
    org_name: str,
    app_id: str,
    app_secret: str,
    sign_type: str,
    private_key: str,
    public_key: str,
    timeout: int,
    remark: str,
    updated_by: str,
) -> InsuranceInterfaceConfig:
    config = get_config(db)
    if not config:
        config = InsuranceInterfaceConfig(id=1)
        db.add(config)
    config.enabled = enabled
    config.base_url = base_url.strip()
    config.upload_path = upload_path.strip() or "/api/inventory/upload"
    config.org_code = org_code.strip()
    config.org_name = org_name.strip()
    config.app_id = app_id.strip()
    # 密钥/私钥留空表示保持原值，避免页面回显明文
    if app_secret:
        config.app_secret = app_secret
    if private_key:
        config.private_key = private_key
    if public_key:
        config.public_key = public_key
    config.sign_type = sign_type or "NONE"
    config.timeout = max(timeout, 1)
    config.remark = remark.strip()
    config.updated_by = updated_by
    config.updated_at = datetime.now()
    db.commit()
    db.refresh(config)
    return config


def masked(value: str, keep: int = 3) -> str:
    if not value:
        return ""
    return "*" * max(len(value) - keep, 0) + value[-keep:]
