from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class ScheduleCreate(BaseModel):
    doctor_id: int
    schedule_date: date
    period: str = Field(pattern="^(morning|afternoon)$")
    capacity: int = Field(gt=0)
    # 出诊诊室（可选，中大型门诊部按诊室排班）
    room_id: int | None = None


class ScheduleResponse(ScheduleCreate):
    id: int
    booked: int
    model_config = ConfigDict(from_attributes=True)


class RegistrationCreate(BaseModel):
    patient_id: int
    doctor_id: int
    schedule_id: int | None = None


class RegistrationResponse(RegistrationCreate):
    id: int
    status: str
    model_config = ConfigDict(from_attributes=True)
