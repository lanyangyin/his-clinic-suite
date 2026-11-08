from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CertificateCreate(BaseModel):
    subject: str = Field(min_length=1, max_length=100)


class CertificateResponse(BaseModel):
    id: int
    serial_no: str
    subject: str
    public_key: str
    status: str
    issued_at: datetime
    revoked_at: datetime | None
    model_config = ConfigDict(from_attributes=True)


class SealCreate(BaseModel):
    certificate_id: int
    encounter_id: int


class SealResponse(BaseModel):
    id: int
    certificate_id: int
    target_type: str
    target_id: int
    content_hash: str
    signature: str
    sealed_at: datetime
    model_config = ConfigDict(from_attributes=True)


class VerifyResponse(BaseModel):
    valid: bool
    reason: str = ""
