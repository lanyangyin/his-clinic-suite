from datetime import datetime

from pydantic import BaseModel, ConfigDict


class UserCreate(BaseModel):
    username: str
    password: str
    role: str
    display_name: str = ""
    employee_id: int | None = None
    doctor_id: int | None = None


class UserResponse(BaseModel):
    id: int
    username: str
    role: str
    display_name: str
    employee_id: int | None = None
    doctor_id: int | None = None
    narcotic_right: bool = False
    is_active: bool = True
    model_config = ConfigDict(from_attributes=True)


class PasswordReset(BaseModel):
    password: str


class UserActiveUpdate(BaseModel):
    active: bool


class NarcoticRightUpdate(BaseModel):
    enabled: bool


class AuditLogResponse(BaseModel):
    id: int
    username: str
    role: str
    method: str
    path: str
    status_code: int
    ip: str = ""
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
