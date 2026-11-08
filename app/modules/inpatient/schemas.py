from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class WardCreate(BaseModel):
    name: str


class WardResponse(WardCreate):
    id: int
    model_config = ConfigDict(from_attributes=True)


class BedCreate(BaseModel):
    ward_id: int
    code: str


class BedResponse(BedCreate):
    id: int
    status: str
    model_config = ConfigDict(from_attributes=True)


class AdmissionCreate(BaseModel):
    patient_id: int
    doctor_id: int
    bed_id: int


class AdmissionResponse(AdmissionCreate):
    id: int
    status: str
    admitted_at: datetime
    discharged_at: datetime | None
    model_config = ConfigDict(from_attributes=True)


class TransferBedRequest(BaseModel):
    bed_id: int


class OrderCreate(BaseModel):
    doctor_id: int
    drug_id: int
    order_type: str = Field(pattern="^(standing|stat)$")
    quantity: int = Field(gt=0)


class OrderResponse(BaseModel):
    id: int
    admission_id: int
    doctor_id: int
    drug_id: int
    drug_name: str
    order_type: str
    quantity: int
    status: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ExecuteRequest(BaseModel):
    note: str = ""


class ExecutionResponse(BaseModel):
    id: int
    order_id: int
    executed_at: datetime
    note: str
    model_config = ConfigDict(from_attributes=True)


class ChargeResponse(BaseModel):
    id: int
    admission_id: int
    execution_id: int
    quantity: int
    unit_price: float
    amount: float
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class BillResponse(BaseModel):
    admission_id: int
    total_amount: float
    charge_count: int


class DispenseRequestResponse(BaseModel):
    id: int
    admission_id: int
    order_id: int
    drug_id: int
    drug_name: str
    quantity: int
    status: str
    created_at: datetime
    dispensed_at: datetime | None
    returned_at: datetime | None
    model_config = ConfigDict(from_attributes=True)


class VitalSignCreate(BaseModel):
    temperature: float | None = Field(default=None, ge=30, le=45)
    pulse: int | None = Field(default=None, ge=20, le=250)
    respiration: int | None = Field(default=None, ge=5, le=60)
    systolic: int | None = Field(default=None, ge=60, le=260)
    diastolic: int | None = Field(default=None, ge=30, le=160)
    spo2: int | None = Field(default=None, ge=50, le=100)

    @model_validator(mode="after")
    def at_least_one(self):
        values = (
            self.temperature,
            self.pulse,
            self.respiration,
            self.systolic,
            self.diastolic,
            self.spo2,
        )
        if all(v is None for v in values):
            raise ValueError("至少需要录入一项体征")
        return self


class VitalSignResponse(VitalSignCreate):
    id: int
    admission_id: int
    recorded_at: datetime
    recorded_by: str
    model_config = ConfigDict(from_attributes=True)


class NursingNoteCreate(BaseModel):
    content: str = Field(min_length=1, max_length=500)


class NursingNoteResponse(BaseModel):
    id: int
    admission_id: int
    content: str
    recorded_at: datetime
    recorded_by: str
    model_config = ConfigDict(from_attributes=True)
