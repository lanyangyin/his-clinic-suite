from sqlalchemy.orm import Session

from .models import SmsMessage


class SmsUnavailable(RuntimeError):
    """短信网关未配置或不可用。"""


def send_sms(db: Session, phone: str, content: str, template: str = "custom") -> SmsMessage:
    """发送短信；未显式允许 Mock 时拒绝伪造 sent。"""
    from app import settings

    gateway_url = (getattr(settings, "SMS_GATEWAY_URL", "") or "").strip()
    if gateway_url:
        import json
        import urllib.request

        payload = json.dumps(
            {"phone": phone, "content": content, "template": template},
            ensure_ascii=False,
        ).encode("utf-8")
        request = urllib.request.Request(
            gateway_url,
            data=payload,
            headers={
                "Content-Type": "application/json; charset=utf-8",
                "Authorization": f"Bearer {getattr(settings, 'SMS_GATEWAY_TOKEN', '')}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                if not 200 <= response.status < 300:
                    raise SmsUnavailable(f"短信网关返回 {response.status}")
        except SmsUnavailable:
            raise
        except Exception as e:
            raise SmsUnavailable(f"短信网关调用失败：{e}") from e
    elif not getattr(settings, "SMS_ALLOW_MOCK", False):
        raise SmsUnavailable("短信网关未配置，已拒绝发送")
    message = SmsMessage(
        phone=phone,
        content=content[:200],
        template=template,
        status="sent",
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


def list_messages(
    db: Session, phone: str | None = None, template: str | None = None
) -> list[SmsMessage]:
    query = db.query(SmsMessage)
    if phone is not None:
        query = query.filter(SmsMessage.phone == phone)
    if template is not None:
        query = query.filter(SmsMessage.template == template)
    return query.order_by(SmsMessage.id.desc()).all()
