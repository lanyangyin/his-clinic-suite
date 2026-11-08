from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.modules.auth.security import require_role

from .schemas import (
    CertificateCreate,
    CertificateResponse,
    SealCreate,
    SealResponse,
    VerifyResponse,
)
from .service import (
    get_certificate,
    get_seal,
    issue_certificate,
    list_certificates,
    list_seals,
    seal_record,
    verify_seal,
)

router = APIRouter(prefix="/ca", tags=["ca"])


@router.post("/certificates", response_model=CertificateResponse, status_code=201)
def new_certificate(
    data: CertificateCreate,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("admin")),
):
    return issue_certificate(db, data)


@router.get("/certificates", response_model=list[CertificateResponse])
def get_certificates(db: Session = Depends(get_db)):
    return list_certificates(db)


@router.get("/certificates/{certificate_id}", response_model=CertificateResponse)
def get_certificate_one(certificate_id: int, db: Session = Depends(get_db)):
    certificate = get_certificate(db, certificate_id)
    if not certificate:
        raise HTTPException(status_code=404, detail="证书不存在")
    return certificate


@router.post("/seals", response_model=SealResponse, status_code=201)
def new_seal(
    data: SealCreate,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("doctor")),
):
    try:
        return seal_record(db, data.encounter_id, data.certificate_id)
    except ValueError as e:
        code = 404 if str(e) in {"就诊记录不存在", "证书不存在", "病历不存在"} else 400
        raise HTTPException(status_code=code, detail=str(e))


@router.get("/seals", response_model=list[SealResponse])
def get_seals(encounter_id: int | None = None, db: Session = Depends(get_db)):
    return list_seals(db, encounter_id)


@router.get("/seals/{seal_id}", response_model=SealResponse)
def get_seal_one(seal_id: int, db: Session = Depends(get_db)):
    seal = get_seal(db, seal_id)
    if not seal:
        raise HTTPException(status_code=404, detail="签章记录不存在")
    return seal


@router.get("/seals/{seal_id}/verify", response_model=VerifyResponse)
def verify(seal_id: int, db: Session = Depends(get_db)):
    try:
        return verify_seal(db, seal_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
