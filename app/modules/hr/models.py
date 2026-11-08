from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Employee(Base):
    __tablename__ = "employees"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    employee_no: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    department_id: Mapped[int | None] = mapped_column(
        ForeignKey("departments.id"), nullable=True
    )
    # 岗位：doctor / nurse / cashier / pharmacist / lab / radiology / admin
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    phone: Mapped[str] = mapped_column(String(20), default="", nullable=False)
    email: Mapped[str] = mapped_column(String(100), default="", nullable=False)
    hired_at: Mapped[date] = mapped_column(Date, nullable=False)
    # active 在职 / resigned 已离职
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    resigned_at: Mapped[date | None] = mapped_column(Date, nullable=True)


class AttendanceRecord(Base):
    __tablename__ = "attendance_records"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id"), nullable=False, index=True
    )
    attendance_date: Mapped[date] = mapped_column(Date, nullable=False)
    # in 上班打卡 / out 下班打卡
    check_type: Mapped[str] = mapped_column(String(10), nullable=False)
    checked_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "employee_id", "attendance_date", "check_type", name="uq_attendance"
        ),
    )


class SalaryRequest(Base):
    __tablename__ = "salary_requests"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id"), nullable=False, index=True
    )
    month: Mapped[str] = mapped_column(String(7), nullable=False)
    base_amount: Mapped[float] = mapped_column(nullable=False)
    bonus_amount: Mapped[float] = mapped_column(
        default=0.0, server_default="0", nullable=False
    )
    total_amount: Mapped[float] = mapped_column(nullable=False)
    # pending 待审批 / approved 已批准 / rejected 已驳回
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    requested_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, nullable=False
    )
    requested_by: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reviewed_by: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    review_note: Mapped[str] = mapped_column(String(200), default="", nullable=False)

    employee = relationship("Employee")

    __table_args__ = (
        UniqueConstraint("employee_id", "month", name="uq_salary_employee_month"),
    )

    @property
    def employee_name(self) -> str:
        return self.employee.name if self.employee else ""


class StaffShift(Base):
    __tablename__ = "staff_shifts"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id"), nullable=False, index=True
    )
    shift_date: Mapped[date] = mapped_column(Date, nullable=False)
    # morning 白班 / afternoon 中班 / night 夜班 / off 休息
    shift_type: Mapped[str] = mapped_column(String(20), nullable=False)

    employee = relationship("Employee")

    __table_args__ = (
        UniqueConstraint("employee_id", "shift_date", name="uq_shift_employee_date"),
    )

    @property
    def employee_name(self) -> str:
        return self.employee.name if self.employee else ""
