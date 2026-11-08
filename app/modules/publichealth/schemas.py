from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ReportCreate(BaseModel):
    encounter_id: int
    disease_code: str = Field(min_length=1, max_length=20)
    disease_name: str = Field(min_length=1, max_length=100)


class ReportResponse(BaseModel):
    id: int
    encounter_id: int
    disease_code: str
    disease_name: str
    status: str
    created_at: datetime
    reported_by: str
    submitted_at: datetime | None
    model_config = ConfigDict(from_attributes=True)
