import uuid

from gmssl import sm2

from app.modules.encounter.service import get_encounter, get_medical_record
from app.modules.insurance.crypto import sm2_sign, sm2_verify, sm3_hex
from sqlalchemy.orm import Session

from .models import CACertificate, CASeal
from .schemas import CertificateCreate


def issue_certificate(db: Session, data: CertificateCreate) -> CACertificate:
    """签发演示 CA 证书：生成 SM2 密钥对与唯一序列号。"""
    private_key = uuid.uuid4().hex[:32]
    helper = sm2.CryptSM2(private_key=private_key, public_key="")
    public_key = helper._kg(
        int(private_key, 16), sm2.default_ecc_table["g"]
    )

    certificate = CACertificate(
        serial_no=uuid.uuid4().hex.upper(),
        subject=data.subject,
        private_key=private_key,
        public_key=public_key,
        status="valid",
    )
    db.add(certificate)
    db.commit()
    db.refresh(certificate)
    return certificate


def get_certificate(db: Session, certificate_id: int) -> CACertificate | None:
    return db.get(CACertificate, certificate_id)


def list_certificates(db: Session) -> list[CACertificate]:
    return db.query(CACertificate).order_by(CACertificate.id).all()


def _record_content(record) -> str:
    """签章内容规范化：病历五要素按固定顺序拼接。"""
    return "|".join(
        [
            record.chief_complaint,
            record.present_illness,
            record.past_history,
            record.physical_exam,
            record.treatment_advice,
        ]
    )


def seal_record(
    db: Session, encounter_id: int, certificate_id: int
) -> CASeal:
    """对病历进行 CA 数字签章：SM3 摘要 + SM2 签名。"""
    certificate = get_certificate(db, certificate_id)
    if not certificate:
        raise ValueError("证书不存在")
    if certificate.status != "valid":
        raise ValueError("证书已吊销")

    if not get_encounter(db, encounter_id):
        raise ValueError("就诊记录不存在")
    record = get_medical_record(db, encounter_id)
    if not record:
        raise ValueError("病历不存在")

    existing = (
        db.query(CASeal)
        .filter(
            CASeal.certificate_id == certificate_id,
            CASeal.target_type == "medical_record",
            CASeal.target_id == encounter_id,
        )
        .first()
    )
    if existing:
        raise ValueError("该病历已用此证书签章")

    content_hash = sm3_hex(_record_content(record).encode())
    signature = sm2_sign(
        content_hash.encode(), certificate.private_key, certificate.public_key
    )

    seal = CASeal(
        certificate_id=certificate_id,
        target_type="medical_record",
        target_id=encounter_id,
        content_hash=content_hash,
        signature=signature,
    )
    db.add(seal)
    db.commit()
    db.refresh(seal)
    return seal


def get_seal(db: Session, seal_id: int) -> CASeal | None:
    return db.get(CASeal, seal_id)


def list_seals(db: Session, encounter_id: int | None = None) -> list[CASeal]:
    query = db.query(CASeal)
    if encounter_id is not None:
        query = query.filter(
            CASeal.target_type == "medical_record", CASeal.target_id == encounter_id
        )
    return query.order_by(CASeal.id).all()


def verify_seal(db: Session, seal_id: int) -> dict:
    """验章：重算当前内容摘要并用证书公钥验签。"""
    seal = get_seal(db, seal_id)
    if not seal:
        raise ValueError("签章记录不存在")

    certificate = get_certificate(db, seal.certificate_id)
    if not certificate:
        return {"valid": False, "reason": "证书不存在"}

    if seal.target_type == "medical_record":
        record = get_medical_record(db, seal.target_id)
        if not record:
            return {"valid": False, "reason": "病历不存在"}
        current_hash = sm3_hex(_record_content(record).encode())
        if current_hash != seal.content_hash:
            return {"valid": False, "reason": "内容已被篡改"}

    valid = sm2_verify(seal.signature, seal.content_hash.encode(), certificate.public_key)
    if not valid:
        return {"valid": False, "reason": "签名校验失败"}
    if certificate.status != "valid":
        return {"valid": False, "reason": "签发证书已吊销"}
    return {"valid": True, "reason": ""}
