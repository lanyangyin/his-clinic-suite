from datetime import datetime

from pydantic import BaseModel, ConfigDict


class UserCreate(BaseModel):
    username: str
    password: str
    role: str
    display_name: str = ""
    employee_id: int | None = None


class UserResponse(BaseModel):
    id: int
    username: str
    role: str
    display_name: str
    employee_id: int | None = None
    model_config = ConfigDict(from_attributes=True)


class AuditLogResponse(BaseModel):
    id: int
    username: str
    role: str
    method: str
    path: str
    status_code: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
