from sqlalchemy.orm import Session

from app import settings

from .models import IntegrationConfig

KEYS = {
    "insurance_upload_url": ("医保处方上传地址", "INSURANCE_PRESCRIPTION_UPLOAD_URL"),
    "insurance_upload_token": ("医保上传 Token", "INSURANCE_PRESCRIPTION_UPLOAD_TOKEN"),
    "wecom_webhook_url": ("企业微信 Webhook", "WECOM_WEBHOOK_URL"),
    "sms_webhook_url": ("短信网关地址", "SMS_WEBHOOK_URL"),
}


def get_value(db: Session | None, key: str) -> str:
    if db is not None:
        row = db.get(IntegrationConfig, key)
        if row and row.value:
            return row.value
    return getattr(settings, KEYS.get(key, ("", ""))[1], "")


def list_values(db: Session) -> list[dict]:
    rows = {row.key: row for row in db.query(IntegrationConfig).all()}
    result = []
    for key, (label, _) in KEYS.items():
        value = get_value(db, key)
        result.append(
            {
                "key": key,
                "label": label,
                "value": value,
                "configured": bool(value),
                "updated_by": rows[key].updated_by if key in rows else "",
                "updated_at": rows[key].updated_at if key in rows else None,
            }
        )
    return result


def set_values(db: Session, values: dict[str, str], operator: str) -> None:
    for key, value in values.items():
        if key not in KEYS:
            continue
        row = db.get(IntegrationConfig, key)
        if not row:
            row = IntegrationConfig(key=key)
            db.add(row)
        row.value = (value or "").strip()
        row.updated_by = operator
        from datetime import datetime

        row.updated_at = datetime.now()
    db.commit()
