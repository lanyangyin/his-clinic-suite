from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.modules.auth.security import require_login, require_read_login, require_role

from .service import dispatch_pending, inbox, mark_read, read_at_for, retry_failed

router = APIRouter(prefix="/notifications", tags=["notifications"], dependencies=[Depends(require_read_login)])


@router.get("")
def my_notifications(
    db: Session = Depends(get_db),
    user=Depends(require_login),
):
    rows = inbox(db, user)
    return [
        {
            "id": row.id,
            "channel": row.channel,
            "title": row.title,
            "body": row.body,
            "status": row.status,
            "biz_type": row.biz_type,
            "biz_id": row.biz_id,
            "created_at": row.created_at,
            "read_at": read_at_for(db, row.id, user.username) or row.read_at,
        }
        for row in rows
    ]


@router.post("/{notification_id}/read")
def read_notification(
    notification_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_login),
):
    try:
        mark_read(db, notification_id, user)
        return {"ok": True}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/retry")
def retry(
    db: Session = Depends(get_db),
    _: None = Depends(require_role("admin")),
):
    return {"retried": retry_failed(db)}


@router.post("/dispatch")
def dispatch(
    db: Session = Depends(get_db),
    _: None = Depends(require_role("admin")),
):
    return dispatch_pending(db)
