from pydantic import BaseModel, ConfigDict

class PatientCreate(BaseModel):
    name: str
    id_number: str
    phone: str | None = None

class PatientResponse(PatientCreate):
    id: int
    model_config = ConfigDict(from_attributes=True)