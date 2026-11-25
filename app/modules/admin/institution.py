"""机构级参数：网页配置，空值回退 config.ini。"""
from datetime import datetime

from sqlalchemy.orm import Session

from app import settings
from app.modules.admin.models import InstitutionSetting

FIELDS = (
    "clinic_name", "clinic_address", "clinic_phone", "insurance_enabled",
    "national_url", "national_token", "national_org_code",
    "national_region_code", "national_operator", "national_mock",
)


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
        "national_mock": row.national_mock or settings.INSURANCE_NATIONAL_MOCK,
    }


def save(db: Session, values: dict, operator: str = "") -> dict:
    row = _row(db)
    for field in FIELDS:
        if field not in values:
            continue
        value = values[field]
        # 密钥留空表示不修改，避免每次保存把已填 token 清空
        if field == "national_token" and not value:
            continue
        setattr(row, field, value)
    row.updated_by = operator
    row.updated_at = datetime.now()
    db.commit()
    db.refresh(row)
    return load(db)
