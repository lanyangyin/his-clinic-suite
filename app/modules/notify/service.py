import json
from datetime import datetime, timedelta
from urllib.request import Request, urlopen

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app import settings

from .models import NotificationOutbox, NotificationRead, NotificationTemplate


def enqueue(
    db: Session,
    *,
    recipient: str,
    title: str,
    body: str,
    biz_type: str = "",
    biz_id: int | None = None,
    channel: str = "internal",
    template_code: str = "",
    template_vars: dict | None = None,
) -> NotificationOutbox:
    if template_code:
        template = (
            db.query(NotificationTemplate)
            .filter(
                NotificationTemplate.code == template_code,
                NotificationTemplate.active.is_(True),
            )
            .first()
        )
        if template:
            values = template_vars or {}
            try:
                title = (template.title or title).format(**values)
                body = (template.body or body).format(**values)
            except (KeyError, IndexError):
                pass
            channel = template.channel or channel
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
    template_code: str = "",
    template_vars: dict | None = None,
) -> None:
    enqueue(
        db,
        recipient=f"role:{role}",
        title=title,
        body=body,
        biz_type=biz_type,
        biz_id=biz_id,
        channel="internal",
        template_code=template_code,
        template_vars=template_vars,
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
    now = datetime.now()
    rows = (
        db.query(NotificationOutbox)
        .filter(
            or_(
                NotificationOutbox.status == "pending",
                and_(
                    NotificationOutbox.status == "failed",
                    NotificationOutbox.attempts < 3,
                    NotificationOutbox.next_retry_at.is_not(None),
                    NotificationOutbox.next_retry_at <= now,
                ),
            )
        )
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
            row.next_retry_at = None
            sent += 1
        except Exception as exc:
            row.status = "failed"
            row.last_error = str(exc)[:300]
            delay = min(30, 2 ** max(1, row.attempts))
            row.next_retry_at = datetime.now() + timedelta(minutes=delay)
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
    read = (
        db.query(NotificationRead)
        .filter(
            NotificationRead.notification_id == notification_id,
            NotificationRead.username == user.username,
        )
        .first()
    )
    if read is None:
        db.add(NotificationRead(notification_id=notification_id, username=user.username))
        # 兼容单用户通知的旧 read_at 字段；角色行不再写全局已读
        if row.recipient == user.username:
            row.read_at = datetime.now()
        db.commit()
    return row


def read_at_for(db: Session, notification_id: int, username: str):
    row = (
        db.query(NotificationRead)
        .filter(
            NotificationRead.notification_id == notification_id,
            NotificationRead.username == username,
        )
        .first()
    )
    return row.read_at if row else None


def retry_failed(db: Session) -> int:
    rows = (
        db.query(NotificationOutbox)
        .filter(
            NotificationOutbox.status == "failed",
            NotificationOutbox.attempts < 3,
            or_(
                NotificationOutbox.next_retry_at.is_(None),
                NotificationOutbox.next_retry_at <= datetime.now(),
            ),
        )
        .all()
    )
    for row in rows:
        row.status = "pending"
        row.last_error = ""
    db.commit()
    return len(rows)
