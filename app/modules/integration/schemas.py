from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class Hl7Message(BaseModel):
    message: str = Field(min_length=1, max_length=4000)


class Hl7Result(BaseModel):
    patient_id: int
    created: bool


class IntegrationLogResponse(BaseModel):
    id: int
    protocol: str
    direction: str
    message_type: str
    summary: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
