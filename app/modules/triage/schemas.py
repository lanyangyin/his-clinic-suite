from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TicketCreate(BaseModel):
    registration_id: int
    # 预检分诊：1 濒危 / 2 危重 / 3 急症 / 4 非急症
    triage_level: int = Field(default=4, ge=1, le=4)
    chief_complaint: str = Field(default="", max_length=200)
    temperature: float | None = Field(default=None, ge=30, le=45)
    pulse: int | None = Field(default=None, ge=20, le=250)
    respiration: int | None = Field(default=None, ge=5, le=60)
    systolic: int | None = Field(default=None, ge=40, le=300)
    diastolic: int | None = Field(default=None, ge=20, le=200)
    spo2: int | None = Field(default=None, ge=50, le=100)
    pain_score: int | None = Field(default=None, ge=0, le=10)
    isolation: bool = False


class TicketResponse(TicketCreate):
    id: int
    status: str
    assessed_by: str
    assessed_at: datetime | None
    vital_summary: str
    bp_display: str
    created_at: datetime
    called_at: datetime | None
    passed_at: datetime | None
    done_at: datetime | None
    model_config = ConfigDict(from_attributes=True)
