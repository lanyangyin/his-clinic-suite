from sqlalchemy.orm import Session

from .models import SmsMessage


def send_sms(db: Session, phone: str, content: str, template: str = "custom") -> SmsMessage:
    """发送短信（Mock 网关：仅落库），返回发送记录。"""
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
