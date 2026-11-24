import hmac
import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app import settings
from app.database import get_db
from app.modules.patient.service import get_patient_by_id_number

from app.modules.sms.service import SmsUnavailable, send_sms
from .models import PortalLoginCode
from .schemas import (
    PortalAccessRequest,
    PortalAccessResponse,
    PortalCodeRequest,
    PortalPatientResponse,
    PortalReportsResponse,
)
from .service import get_portal_patient, get_portal_reports
from .token import hash_code, issue_token, verify_token

router = APIRouter(prefix="/portal", tags=["portal"])


def _require_access(id_number: str, x_portal_token: str = Header(default="")) -> None:
    if getattr(settings, "ALLOW_ANONYMOUS_READ", False):
        return
    if not x_portal_token or not verify_token(x_portal_token, id_number):
        raise HTTPException(status_code=401, detail="患者门户令牌缺失或已过期")


def _consume_code(db: Session, data: PortalAccessRequest) -> bool:
    row = (
        db.query(PortalLoginCode)
        .filter(
            PortalLoginCode.id_number == data.id_number,
            PortalLoginCode.phone == data.phone.strip(),
            PortalLoginCode.used.is_(False),
            PortalLoginCode.expires_at >= datetime.now(),
        )
        .order_by(PortalLoginCode.id.desc())
        .first()
    )
    if not row or row.attempts >= 5:
        return False
    supplied = data.code.strip()
    if not hmac.compare_digest(row.code_hash, hash_code(data.id_number, row.phone, supplied)):
        row.attempts += 1
        db.commit()
        return False
    row.used = True
    db.commit()
    return True


@router.post("/request-code")
def request_portal_code(data: PortalCodeRequest, db: Session = Depends(get_db)):
    """发送一次性门户验证码；无论账号是否存在都返回同样结果，避免枚举。"""
    patient = get_patient_by_id_number(db, data.id_number)
    if patient and patient.phone and patient.phone == data.phone.strip():
        recent = (
            db.query(PortalLoginCode)
            .filter(
                PortalLoginCode.id_number == data.id_number,
                PortalLoginCode.phone == data.phone.strip(),
                PortalLoginCode.created_at >= datetime.now() - timedelta(seconds=60),
            )
            .first()
        )
        if recent:
            return {"sent": True, "expires_in": 300}
        db.query(PortalLoginCode).filter(
            PortalLoginCode.id_number == data.id_number,
            PortalLoginCode.used.is_(False),
        ).update({PortalLoginCode.used: True}, synchronize_session=False)
        code = f"{secrets.randbelow(1_000_000):06d}"
        db.add(
            PortalLoginCode(
                id_number=data.id_number,
                phone=data.phone.strip(),
                code_hash=hash_code(data.id_number, data.phone.strip(), code),
                expires_at=datetime.now() + timedelta(minutes=5),
            )
        )
        db.flush()
        try:
            send_sms(
                db,
                data.phone.strip(),
                f"【HIS】患者门户验证码 {code}，5 分钟内有效，请勿转发。",
                "portal_otp",
            )
        except SmsUnavailable:
            db.rollback()
            raise HTTPException(status_code=503, detail="短信服务未配置")
    return {"sent": True, "expires_in": 300}


@router.post("/access", response_model=PortalAccessResponse)
def portal_access(data: PortalAccessRequest, db: Session = Depends(get_db)):
    patient = get_patient_by_id_number(db, data.id_number)
    if not patient or not patient.phone or patient.phone != data.phone.strip():
        raise HTTPException(status_code=401, detail="身份证号或手机号不匹配")
    if getattr(settings, "PORTAL_REQUIRE_OTP", False):
        if not data.code.strip() or not _consume_code(db, data):
            raise HTTPException(status_code=401, detail="验证码错误或已过期")
    return {"token": issue_token(data.id_number), "expires_in": 600}


@router.get("/patients/{id_number}", response_model=PortalPatientResponse)
def patient_portal(
    id_number: str,
    db: Session = Depends(get_db),
    x_portal_token: str = Header(default=""),
):
    """患者自助查询；生产需短时门户令牌。"""
    _require_access(id_number, x_portal_token)
    try:
        return get_portal_patient(db, id_number)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/reports/{id_number}", response_model=PortalReportsResponse)
def patient_reports(
    id_number: str,
    db: Session = Depends(get_db),
    x_portal_token: str = Header(default=""),
):
    """患者自助查询已出结果的检验/检查报告。"""
    _require_access(id_number, x_portal_token)
    try:
        return get_portal_reports(db, id_number)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
