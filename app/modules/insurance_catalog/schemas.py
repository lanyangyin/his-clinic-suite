from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class InsuranceDrugResponse(BaseModel):
    id: int
    national_code: str
    name: str
    dosage_form: str
    spec: str
    manufacturer: str
    unit: str
    category: str
    reimbursement_note: str
    approval_no: str
    valid_from: date | None
    valid_to: date | None
    source_version: str
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class CatalogImportResult(BaseModel):
    # created 已导入 / unchanged 内容未变化 / skipped 无有效行
    status: str
    version: str | None = None
    inserted: int = 0
    updated: int = 0
    skipped: int = 0
    row_count: int = 0
    checksum: str = ""


class CatalogVersionResponse(BaseModel):
    id: int
    version: str
    source: str
    file_name: str
    row_count: int
    checksum: str
    imported_by: str
    imported_at: datetime
    model_config = ConfigDict(from_attributes=True)


class CatalogSyncRequest(BaseModel):
    url: str = Field(min_length=1, max_length=500)
