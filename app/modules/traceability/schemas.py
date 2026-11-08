from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TraceScanRequest(BaseModel):
    codes: list[str] = Field(min_length=1)
    drug_id: int | None = None
    batch_no: str = ""
    ref_id: int | None = None
    target_warehouse: str = "药房"
    encounter_id: int | None = None


class TraceCodeResponse(BaseModel):
    id: int
    trace_code: str
    drug_id: int
    batch_no: str
    warehouse: str
    status: str
    ref_type: str
    ref_id: int | None
    patient_id: int | None
    encounter_id: int | None
    scanned_by: str
    scanned_at: datetime
    note: str
    model_config = ConfigDict(from_attributes=True)


class TraceScanResult(BaseModel):
    accepted: int
    status: str
    message: str
    codes: list[str]
