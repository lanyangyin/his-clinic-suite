from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PathwayCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    diagnosis: str = Field(min_length=1, max_length=200)


class PathwayResponse(PathwayCreate):
    id: int
    model_config = ConfigDict(from_attributes=True)


class EnrollRequest(BaseModel):
    admission_id: int


class EnrollmentResponse(BaseModel):
    id: int
    pathway_id: int
    admission_id: int
    status: str
    enrolled_at: datetime
    completed_at: datetime | None
    model_config = ConfigDict(from_attributes=True)


class VarianceCreate(BaseModel):
    reason: str = Field(min_length=1, max_length=200)


class VarianceResponse(BaseModel):
    id: int
    enrollment_id: int
    reason: str
    noted_at: datetime
    noted_by: str
    model_config = ConfigDict(from_attributes=True)
