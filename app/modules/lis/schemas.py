from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class LabItemCreate(BaseModel):
    code: str = Field(min_length=1, max_length=20)
    name: str = Field(min_length=1, max_length=100)
    price: float = Field(default=0, ge=0)
    specimen_type: str = Field(default="血液", max_length=30)
    unit: str = Field(default="", max_length=20)
    reference_low: float | None = None
    reference_high: float | None = None
    method: str = Field(default="", max_length=50)
    tat_minutes: int = Field(default=60, ge=1, le=10080)
    insurance_ratio: float = Field(default=0.7, ge=0, le=1)
    result_kind: str = Field(default="numeric", pattern="^(numeric|text)$")


class LabItemResponse(LabItemCreate):
    id: int
    model_config = ConfigDict(from_attributes=True)


class LabRequestCreate(BaseModel):
    item_id: int
    priority: str = Field(default="routine", pattern="^(routine|urgent)$")


class LabReportRequest(BaseModel):
    result: str = Field(default="", max_length=500)
    result_value: float | None = None
    result_unit: str = Field(default="", max_length=20)
    reference_low: float | None = None
    reference_high: float | None = None
    abnormal_flag: str = Field(default="", pattern="^(|H|L|N)$")
    critical_flag: bool = False
    critical_note: str = Field(default="", max_length=200)
    critical_notified_to: str = Field(default="", max_length=100)

    @model_validator(mode="after")
    def require_result(self):
        if not self.result.strip() and self.result_value is None:
            raise ValueError("请填写检验结果")
        return self


class SpecimenActionRequest(BaseModel):
    note: str = Field(default="", max_length=200)


class RejectRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=200)


class CriticalRequest(BaseModel):
    note: str = Field(min_length=1, max_length=200)
    notified_to: str = Field(default="", max_length=100)


class LabRequestResponse(BaseModel):
    id: int
    encounter_id: int
    item_id: int
    item_name: str
    status: str
    priority: str
    specimen_no: str | None
    specimen_type: str
    requested_by: str
    requested_at: datetime
    collected_at: datetime | None
    collected_by: str
    received_at: datetime | None
    received_by: str
    testing_at: datetime | None
    testing_by: str
    reported_at: datetime | None
    report_no: str | None
    reviewed_at: datetime | None
    reviewed_by: str
    reject_reason: str | None
    result: str | None
    result_value: float | None
    result_unit: str
    reference_low: float | None
    reference_high: float | None
    abnormal_flag: str
    critical_flag: bool
    critical_note: str | None
    critical_notified_to: str | None
    critical_notified_at: datetime | None
    result_display: str
    model_config = ConfigDict(from_attributes=True)
