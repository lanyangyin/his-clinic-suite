from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.modules.auth.security import require_role

from .schemas import SmsResponse, SmsSend
from .service import list_messages, send_sms

router = APIRouter(prefix="/sms", tags=["sms"])


@router.post("/send", response_model=SmsResponse, status_code=201)
def send(
    data: SmsSend,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("admin")),
):
    return send_sms(db, data.phone, data.content, data.template)


@router.get("/messages", response_model=list[SmsResponse])
def get_messages(
    phone: str | None = None,
    template: str | None = None,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("admin")),
):
    return list_messages(db, phone, template)
