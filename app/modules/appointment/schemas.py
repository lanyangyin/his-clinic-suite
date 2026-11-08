from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AppointmentCreate(BaseModel):
    patient_id: int
    doctor_id: int
    schedule_id: int


class AppointmentResponse(BaseModel):
    id: int
    patient_id: int
    doctor_id: int
    schedule_id: int
    registration_id: int | None
    status: str
    created_by: str
    created_at: datetime
    checked_in_at: datetime | None
    model_config = ConfigDict(from_attributes=True)
