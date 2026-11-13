from pydantic import BaseModel, ConfigDict


class DepartmentCreate(BaseModel):
    name: str


class DepartmentResponse(DepartmentCreate):
    id: int
    active: bool = True
    model_config = ConfigDict(from_attributes=True)


class DoctorCreate(BaseModel):
    name: str
    department_id: int


class DoctorResponse(DoctorCreate):
    id: int
    active: bool = True
    model_config = ConfigDict(from_attributes=True)
