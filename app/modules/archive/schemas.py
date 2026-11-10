from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class ArchiveRecordCreate(BaseModel):
    patient_id: int
    encounter_id: int | None = None
    record_type: str = Field(default="outpatient", pattern="^(outpatient|inpatient|emergency)$")
    page_count: int = Field(default=0, ge=0)
    storage_location: str = Field(default="", max_length=100)
    note: str = Field(default="", max_length=200)


class ArchiveCompleteRequest(BaseModel):
    storage_location: str = Field(min_length=1, max_length=100)
    page_count: int = Field(gt=0)
    completeness: str = Field(default="complete", pattern="^(complete|incomplete)$")
    note: str = Field(default="", max_length=200)


class BorrowCreate(BaseModel):
    borrower: str = Field(min_length=1, max_length=50)
    department: str = Field(default="", max_length=50)
    purpose: str = Field(default="", max_length=200)
    due_days: int = Field(default=7, ge=1, le=365)
    note: str = Field(default="", max_length=200)


class BorrowResponse(BaseModel):
    id: int
    record_id: int
    borrower: str
    department: str
    purpose: str
    borrowed_at: datetime
    due_at: date | None
    returned_at: datetime | None
    approver: str
    status: str
    note: str
    model_config = ConfigDict(from_attributes=True)


class CopyCreate(BaseModel):
    applicant: str = Field(min_length=1, max_length=50)
    id_number: str = Field(default="", max_length=30)
    relationship: str = Field(default="本人", max_length=30)
    purpose: str = Field(default="", max_length=200)
    contents: str = Field(default="", max_length=200)
    copies: int = Field(default=1, ge=1, le=100)


class CopyCompleteRequest(BaseModel):
    fee: float = Field(default=0, ge=0)


class CopyResponse(BaseModel):
    id: int
    record_id: int
    applicant: str
    id_number: str
    relationship: str
    purpose: str
    contents: str
    copies: int
    fee: float
    status: str
    operator: str
    created_at: datetime
    completed_at: datetime | None
    model_config = ConfigDict(from_attributes=True)


class SealCreate(BaseModel):
    reason: str = Field(min_length=1, max_length=200)
    witness: str = Field(default="", max_length=50)


class SealResponse(BaseModel):
    id: int
    record_id: int
    action: str
    reason: str
    witness: str
    operator: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class DestroyCreate(BaseModel):
    reason: str = Field(min_length=1, max_length=200)
    approved_by: str = Field(min_length=1, max_length=50)
    note: str = Field(default="", max_length=200)


class ArchiveRecordResponse(BaseModel):
    id: int
    archive_no: str | None
    patient_id: int
    patient_name: str
    encounter_id: int | None
    record_type: str
    page_count: int
    status: str
    completeness: str
    storage_location: str
    archived_at: datetime | None
    archived_by: str
    note: str
    created_at: datetime
    active_borrowing_id: int | None = None
    model_config = ConfigDict(from_attributes=True)

class DestructionRequestCreate(BaseModel):
    reason: str = Field(min_length=1, max_length=200)
    note: str = Field(default="", max_length=500)


class DestructionDecision(BaseModel):
    note: str = Field(default="", max_length=200)


class DestructionExecute(BaseModel):
    witness: str = Field(min_length=1, max_length=50)
    note: str = Field(default="", max_length=200)


class DestructionRequestResponse(BaseModel):
    id: int
    record_id: int
    archive_no: str
    patient_name: str
    reason: str
    note: str
    status: str
    requested_by: str
    requested_at: datetime
    approver: str
    approved_at: datetime | None
    approval_note: str
    executed_by: str
    executed_at: datetime | None
    witness: str
    attachment_path: str = ""
    attachment_name: str = ""
    model_config = ConfigDict(from_attributes=True)
