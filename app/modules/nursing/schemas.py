from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PrepareRequest(BaseModel):
    solvent: str = Field(default="", max_length=50)
    dose: str = Field(default="", max_length=50)
    batch_no: str = Field(default="", max_length=50)
    checked_by: str = Field(default="", max_length=50)
    expires_minutes: int = Field(default=120, ge=1, le=1440)
    note: str = Field(default="", max_length=200)


class StartRequest(BaseModel):
    seat_no: str = Field(default="", max_length=20)
    rate_ml_h: float | None = Field(default=None, ge=0, le=1000)


class ObserveRequest(BaseModel):
    rate_ml_h: float | None = Field(default=None, ge=0, le=1000)
    note: str = Field(default="", max_length=200)
    adverse_reaction: str = Field(default="", max_length=200)


class CompleteRequest(BaseModel):
    note: str = Field(default="", max_length=200)
    adverse_reaction: str = Field(default="", max_length=200)


class SkipRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=200)


class NursingOrderResponse(BaseModel):
    id: int
    encounter_id: int
    source_type: str
    source_id: int
    order_type: str
    item_name: str
    high_alert: bool = False
    dosage: str
    route: str
    frequency: str
    status: str
    priority: str
    seat_no: str
    rate_ml_h: float | None
    prepared_by: str
    prepared_at: datetime | None
    started_at: datetime | None
    completed_at: datetime | None
    executed_by: str
    adverse_reaction: str | None
    note: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ObservationResponse(BaseModel):
    id: int
    order_id: int
    observed_at: datetime
    rate_ml_h: float | None
    note: str
    adverse_reaction: str | None
    nurse: str
    model_config = ConfigDict(from_attributes=True)


class PreparationResponse(BaseModel):
    id: int
    order_id: int
    solvent: str
    dose: str
    batch_no: str
    prepared_by: str
    checked_by: str
    prepared_at: datetime
    expires_at: datetime | None
    note: str
    model_config = ConfigDict(from_attributes=True)
