from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class EmployeeCreate(BaseModel):
    employee_no: str = Field(min_length=1, max_length=30)
    name: str = Field(min_length=1, max_length=50)
    department_id: int | None = None
    role: str = Field(min_length=1, max_length=20)
    phone: str = Field(default="", max_length=20)
    email: str = Field(default="", max_length=100)
    hired_at: date


class EmployeeResponse(EmployeeCreate):
    id: int
    status: str
    resigned_at: date | None
    model_config = ConfigDict(from_attributes=True)


class AttendanceCreate(BaseModel):
    employee_id: int
    check_type: str = Field(pattern="^(in|out)$")
    attendance_date: date | None = None


class AttendanceResponse(BaseModel):
    id: int
    employee_id: int
    attendance_date: date
    check_type: str
    checked_at: datetime
    model_config = ConfigDict(from_attributes=True)


class AttendanceSummary(BaseModel):
    employee_id: int
    month: str
    present_days: int


class SalaryRequestCreate(BaseModel):
    employee_id: int
    month: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    base_amount: float = Field(ge=0)
    bonus_amount: float = Field(default=0, ge=0)


class SalaryReviewRequest(BaseModel):
    note: str = Field(default="", max_length=200)


class SalaryRequestResponse(BaseModel):
    id: int
    employee_id: int
    employee_name: str
    month: str
    base_amount: float
    bonus_amount: float
    total_amount: float
    status: str
    requested_at: datetime
    requested_by: str
    reviewed_at: datetime | None
    reviewed_by: str
    review_note: str
    model_config = ConfigDict(from_attributes=True)


class ShiftCreate(BaseModel):
    employee_id: int
    shift_date: date
    shift_type: str = Field(pattern="^(morning|afternoon|night|off)$")


class ShiftResponse(BaseModel):
    id: int
    employee_id: int
    employee_name: str
    shift_date: date
    shift_type: str
    model_config = ConfigDict(from_attributes=True)
