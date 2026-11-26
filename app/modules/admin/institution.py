"""机构级参数：网页配置，空值回退 config.ini。"""
from datetime import datetime

from sqlalchemy.orm import Session

from app import settings
from app.modules.admin.models import InstitutionSetting

FIELDS = (
    "clinic_name", "clinic_address", "clinic_phone", "insurance_enabled",
    "national_url", "national_token", "national_org_code",
    "national_region_code", "national_operator", "national_org_name",
    "national_infver", "national_recer_sys_code", "national_mdtrtarea_code",
    "national_insuplc_code", "national_med_type", "national_sign_type",
    "national_security_mode", "national_timeout", "national_retry",
    "national_dev_no", "national_dev_safe_info", "national_cert_path",
    "national_cert_password", "national_sm2_private_key",
    "national_sm2_public_key", "national_sm4_key", "national_mock",
)
SECRET_FIELDS = {
    "national_token", "national_cert_password",
    "national_sm2_private_key", "national_sm4_key",
}
INT_FIELDS = {"national_timeout", "national_retry"}


def _row(db: Session) -> InstitutionSetting:
    row = db.get(InstitutionSetting, 1)
    if row is None:
        row = InstitutionSetting(id=1)
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


def load(db: Session) -> dict:
    row = _row(db)
    return {
        "clinic_name": row.clinic_name or settings.CLINIC_NAME,
        "clinic_address": row.clinic_address or settings.CLINIC_ADDRESS,
        "clinic_phone": row.clinic_phone or settings.CLINIC_PHONE,
        "insurance_enabled": row.insurance_enabled or settings.INSURANCE_ENABLED,
        "national_url": row.national_url or settings.INSURANCE_NATIONAL_URL,
        "national_token": row.national_token or settings.INSURANCE_NATIONAL_TOKEN,
        "national_org_code": row.national_org_code or settings.INSURANCE_NATIONAL_ORG_CODE,
        "national_region_code": row.national_region_code or settings.INSURANCE_NATIONAL_REGION_CODE,
        "national_operator": row.national_operator or settings.INSURANCE_NATIONAL_OPERATOR,
        "national_org_name": row.national_org_name or settings.INSURANCE_NATIONAL_ORG_NAME,
        "national_infver": row.national_infver or settings.INSURANCE_NATIONAL_INFVER,
        "national_recer_sys_code": row.national_recer_sys_code or settings.INSURANCE_NATIONAL_RECER_SYS_CODE,
        "national_mdtrtarea_code": row.national_mdtrtarea_code or settings.INSURANCE_NATIONAL_MDTRTAREA_CODE,
        "national_insuplc_code": row.national_insuplc_code or settings.INSURANCE_NATIONAL_INSUPLC_CODE,
        "national_med_type": row.national_med_type or settings.INSURANCE_NATIONAL_MED_TYPE,
        "national_sign_type": row.national_sign_type or settings.INSURANCE_NATIONAL_SIGN_TYPE,
        "national_security_mode": row.national_security_mode or settings.INSURANCE_NATIONAL_SECURITY_MODE,
        "national_timeout": row.national_timeout or settings.INSURANCE_NATIONAL_TIMEOUT,
        "national_retry": row.national_retry or settings.INSURANCE_NATIONAL_RETRY,
        "national_dev_no": row.national_dev_no or settings.INSURANCE_NATIONAL_DEV_NO,
        "national_dev_safe_info": row.national_dev_safe_info or settings.INSURANCE_NATIONAL_DEV_SAFE_INFO,
        "national_cert_path": row.national_cert_path or settings.INSURANCE_NATIONAL_CERT_PATH,
        "national_cert_password": row.national_cert_password or settings.INSURANCE_NATIONAL_CERT_PASSWORD,
        "national_sm2_private_key": row.national_sm2_private_key or settings.INSURANCE_NATIONAL_SM2_PRIVATE_KEY,
        "national_sm2_public_key": row.national_sm2_public_key or settings.INSURANCE_NATIONAL_SM2_PUBLIC_KEY,
        "national_sm4_key": row.national_sm4_key or settings.INSURANCE_NATIONAL_SM4_KEY,
        "national_mock": row.national_mock or settings.INSURANCE_NATIONAL_MOCK,
    }


def save(db: Session, values: dict, operator: str = "") -> dict:
    row = _row(db)
    for field in FIELDS:
        if field not in values:
            continue
        value = values[field]
        # 密钥留空表示不修改，避免每次保存把已填 token 清空
        if field in SECRET_FIELDS and not value:
            continue
        if field in INT_FIELDS:
            try:
                value = int(value or 0)
            except (TypeError, ValueError):
                value = 0
        setattr(row, field, value)
    row.updated_by = operator
    row.updated_at = datetime.now()
    db.commit()
    db.refresh(row)
    return load(db)
