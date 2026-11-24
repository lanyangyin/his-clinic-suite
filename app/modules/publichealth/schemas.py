from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class ReportCreate(BaseModel):
    encounter_id: int
    disease_code: str = Field(min_length=1, max_length=20)
    disease_name: str = Field(min_length=1, max_length=100)
    report_type: str = Field(default="clinical", pattern="^(confirmed|suspected|clinical)$")
    onset_date: date | None = None
    diagnosis_date: date | None = None
    report_unit: str = Field(default="", max_length=100)
    reporter_phone: str = Field(default="", max_length=20)
    is_correction: bool = False
    correction_reason: str = Field(default="", max_length=200)
    is_death: bool = False
    death_date: date | None = None


class ReportResponse(BaseModel):
    id: int
    encounter_id: int
    disease_code: str
    disease_name: str
    status: str
    created_at: datetime
    reported_by: str
    submitted_at: datetime | None
    receipt_no: str = ""
    submit_error: str = ""
    report_type: str = "clinical"
    onset_date: date | None = None
    diagnosis_date: date | None = None
    report_unit: str = ""
    reporter_phone: str = ""
    is_correction: bool = False
    correction_reason: str = ""
    is_death: bool = False
    death_date: date | None = None
    model_config = ConfigDict(from_attributes=True)
