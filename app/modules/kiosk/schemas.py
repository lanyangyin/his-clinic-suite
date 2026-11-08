from pydantic import BaseModel, ConfigDict, Field


class KioskRegistrationCreate(BaseModel):
    patient_id_number: str = Field(min_length=1, max_length=18)
    doctor_id: int
    schedule_id: int | None = None


class KioskRegistrationResponse(BaseModel):
    id: int
    patient_id: int
    doctor_id: int
    status: str
    schedule_id: int | None
    model_config = ConfigDict(from_attributes=True)


class KioskPaymentCreate(BaseModel):
    encounter_id: int


class KioskPaymentResponse(BaseModel):
    id: int
    encounter_id: int
    amount: float
    status: str
    insurance_amount: float
    self_pay_amount: float
    model_config = ConfigDict(from_attributes=True)
