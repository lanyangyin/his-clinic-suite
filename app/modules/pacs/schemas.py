from datetime import datetime

import re

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ImagingItemCreate(BaseModel):
    code: str = Field(min_length=1, max_length=20)
    name: str = Field(min_length=1, max_length=100)
    body_part: str = Field(default="", max_length=50)
    price: float = Field(default=0, ge=0)
    insurance_ratio: float = Field(default=0.7, ge=0, le=1)


class ImagingItemResponse(ImagingItemCreate):
    id: int
    model_config = ConfigDict(from_attributes=True)


class ImagingTemplateCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    body_part: str = Field(default="", max_length=50)
    findings: str = Field(default="", max_length=1000)
    impression: str = Field(default="", max_length=500)


class ImagingTemplateResponse(ImagingTemplateCreate):
    id: int
    active: bool
    model_config = ConfigDict(from_attributes=True)


class ImagingRequestCreate(BaseModel):
    item_id: int
    priority: str = Field(default="routine", pattern="^(routine|urgent)$")


class ImagingReportRequest(BaseModel):
    @field_validator("image_url", mode="before")
    @classmethod
    def _validate_image_url(cls, value):
        text = (value or "").strip()
        if text and not (text.startswith("http://") or text.startswith("https://")):
            raise ValueError("PACS 图像地址必须是 http(s) URL")
        return text

    @field_validator("study_uid", "series_uid", mode="before")
    @classmethod
    def _validate_dicom_uid(cls, value):
        text = (value or "").strip()
        if not text:
            return ""
        if len(text) > 64 or not re.fullmatch(r"[0-9]+(?:\.[0-9]+)*", text):
            raise ValueError("DICOM UID 必须是 64 位以内的数字和点号")
        return text

    report: str = Field(default="", max_length=1000)
    findings: str = Field(default="", max_length=1000)
    impression: str = Field(default="", max_length=500)
    template_name: str = Field(default="", max_length=100)
    image_url: str = Field(default="", max_length=200)
    study_uid: str = Field(default="", max_length=64)
    series_uid: str = Field(default="", max_length=64)
    modality: str = Field(default="", max_length=20)
    measurements: str = Field(default="", max_length=500)


class ImagingReviewRequest(BaseModel):
    approve: bool
    note: str = Field(default="", max_length=200)


class ImagingRequestResponse(BaseModel):
    id: int
    encounter_id: int
    item_id: int
    item_name: str
    accession_no: str
    status: str
    priority: str = "routine"
    requested_by: str
    requested_at: datetime
    reported_at: datetime | None
    reported_by: str = ""
    reviewed_by: str = ""
    reviewed_at: datetime | None = None
    review_note: str = ""
    report: str | None
    findings: str = ""
    impression: str = ""
    template_name: str = ""
    image_url: str
    study_uid: str = ""
    series_uid: str = ""
    modality: str = ""
    measurements: str = ""
    model_config = ConfigDict(from_attributes=True)
