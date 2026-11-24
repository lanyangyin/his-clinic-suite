import json
from datetime import datetime
from urllib.request import Request, urlopen

from sqlalchemy.orm import Session

from app import settings

from .models import NotificationOutbox


def enqueue(
    db: Session,
    *,
    recipient: str,
    title: str,
    body: str,
    biz_type: str = "",
    biz_id: int | None = None,
    channel: str = "internal",
) -> NotificationOutbox:
    row = NotificationOutbox(
        biz_type=biz_type,
        biz_id=biz_id,
        channel=channel,
        recipient=recipient,
        title=title,
        body=body,
    )
    db.add(row)
    db.flush()
    return row


def notify_role(
    db: Session,
    role: str,
    title: str,
    body: str,
    *,
    biz_type: str = "",
    biz_id: int | None = None,
) -> None:
    enqueue(
        db,
        recipient=f"role:{role}",
        title=title,
        body=body,
        biz_type=biz_type,
        biz_id=biz_id,
        channel="internal",
    )
    from app.modules.integrations.service import get_value

    if get_value(db, "wecom_webhook_url"):
        enqueue(
            db,
            recipient=f"role:{role}",
            title=title,
            body=body,
            biz_type=biz_type,
            biz_id=biz_id,
            channel="wecom",
        )
    if get_value(db, "sms_webhook_url"):
        enqueue(
            db,
            recipient=f"role:{role}",
            title=title,
            body=body,
            biz_type=biz_type,
            biz_id=biz_id,
            channel="sms",
        )


def _post(url: str, payload: dict) -> None:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = Request(url, data=data, method="POST", headers={"Content-Type": "application/json"})
    with urlopen(req, timeout=8) as response:
        response.read()


def dispatch_pending(db: Session, limit: int = 100) -> dict:
    rows = (
        db.query(NotificationOutbox)
        .filter(NotificationOutbox.status == "pending")
        .order_by(NotificationOutbox.id)
        .limit(limit)
        .all()
    )
    sent = failed = 0
    for row in rows:
        row.attempts += 1
        try:
            if row.channel == "internal":
                pass
            elif row.channel == "wecom":
                from app.modules.integrations.service import get_value

                url = get_value(db, "wecom_webhook_url")
                if not url:
                    raise ValueError("未配置企业微信 Webhook")
                _post(url, {"msgtype": "text", "text": {"content": f"{row.title}\n{row.body}"}})
            elif row.channel == "sms":
                from app.modules.integrations.service import get_value

                url = get_value(db, "sms_webhook_url")
                if not url:
                    raise ValueError("未配置短信网关")
                _post(url, {"recipient": row.recipient, "content": f"{row.title}\n{row.body}"})
            else:
                raise ValueError(f"未知通知渠道：{row.channel}")
            row.status = "sent"
            row.sent_at = datetime.now()
            row.last_error = ""
            sent += 1
        except Exception as exc:
            row.status = "failed"
            row.last_error = str(exc)[:300]
            failed += 1
    db.commit()
    return {"processed": len(rows), "sent": sent, "failed": failed}


def inbox(db: Session, user, include_all: bool = False) -> list[NotificationOutbox]:
    query = db.query(NotificationOutbox)
    if not include_all:
        query = query.filter(
            (NotificationOutbox.recipient == f"role:{user.role}")
            | (NotificationOutbox.recipient == user.username)
        )
    return query.order_by(NotificationOutbox.id.desc()).limit(200).all()


def mark_read(db: Session, notification_id: int, user) -> NotificationOutbox:
    row = db.get(NotificationOutbox, notification_id)
    if not row:
        raise ValueError("通知不存在")
    if user.role != "admin" and row.recipient not in (f"role:{user.role}", user.username):
        raise ValueError("无权操作该通知")
    row.status = "read"
    row.read_at = datetime.now()
    db.commit()
    db.refresh(row)
    return row


def retry_failed(db: Session) -> int:
    rows = (
        db.query(NotificationOutbox)
        .filter(NotificationOutbox.status == "failed")
        .all()
    )
    for row in rows:
        row.status = "pending"
        row.last_error = ""
    db.commit()
    return len(rows)
