from datetime import date, datetime

from sqlalchemy.orm import Session

from .models import AttendanceRecord, Employee, SalaryRequest, StaffShift
from .schemas import AttendanceCreate, EmployeeCreate, SalaryRequestCreate, ShiftCreate


def create_employee(db: Session, data: EmployeeCreate) -> Employee:
    """建立员工档案：工号唯一。"""
    existing = db.query(Employee).filter(Employee.employee_no == data.employee_no).first()
    if existing:
        raise ValueError("工号已存在")

    employee = Employee(**data.model_dump(), status="active")
    db.add(employee)
    db.commit()
    db.refresh(employee)
    return employee


def get_employee(db: Session, employee_id: int) -> Employee | None:
    return db.get(Employee, employee_id)


def list_employees(
    db: Session, status: str | None = None, department_id: int | None = None
) -> list[Employee]:
    query = db.query(Employee)
    if status is not None:
        query = query.filter(Employee.status == status)
    if department_id is not None:
        query = query.filter(Employee.department_id == department_id)
    return query.order_by(Employee.id).all()


def resign(db: Session, employee_id: int, resign_date: date | None = None) -> Employee:
    """办理离职：仅在职员工可离职。"""
    employee = get_employee(db, employee_id)
    if not employee:
        raise ValueError("员工不存在")
    if employee.status != "active":
        raise ValueError("该员工已离职")

    employee.status = "resigned"
    employee.resigned_at = resign_date or date.today()
    db.commit()
    db.refresh(employee)
    return employee


def check_attendance(db: Session, data: AttendanceCreate) -> AttendanceRecord:
    """考勤打卡：同员工同日同类型仅一次，离职员工不能打卡。"""
    employee = get_employee(db, data.employee_id)
    if not employee:
        raise ValueError("员工不存在")
    if employee.status != "active":
        raise ValueError("该员工已离职，不能打卡")

    attendance_date = data.attendance_date or date.today()
    existing = (
        db.query(AttendanceRecord)
        .filter(
            AttendanceRecord.employee_id == data.employee_id,
            AttendanceRecord.attendance_date == attendance_date,
            AttendanceRecord.check_type == data.check_type,
        )
        .first()
    )
    if existing:
        raise ValueError("该员工当日该类型已打卡")

    record = AttendanceRecord(
        employee_id=data.employee_id,
        attendance_date=attendance_date,
        check_type=data.check_type,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def list_attendance(
    db: Session, employee_id: int | None = None, attendance_date: date | None = None
) -> list[AttendanceRecord]:
    query = db.query(AttendanceRecord)
    if employee_id is not None:
        query = query.filter(AttendanceRecord.employee_id == employee_id)
    if attendance_date is not None:
        query = query.filter(AttendanceRecord.attendance_date == attendance_date)
    return query.order_by(AttendanceRecord.id).all()


def attendance_summary(db: Session, employee_id: int, month: str) -> dict:
    """月度考勤汇总：出勤天数（有打卡记录的日期数）。"""
    year, mon = (int(part) for part in month.split("-"))
    start = date(year, mon, 1)
    end = date(year + (mon == 12), (mon % 12) + 1, 1)

    records = (
        db.query(AttendanceRecord)
        .filter(
            AttendanceRecord.employee_id == employee_id,
            AttendanceRecord.attendance_date >= start,
            AttendanceRecord.attendance_date < end,
        )
        .all()
    )
    present_days = len({record.attendance_date for record in records})
    return {
        "employee_id": employee_id,
        "month": month,
        "present_days": present_days,
    }


def create_salary_request(
    db: Session, data: SalaryRequestCreate, requested_by: str = ""
) -> SalaryRequest:
    """发起薪资发放申请：在职员工、同月唯一。"""
    employee = get_employee(db, data.employee_id)
    if not employee:
        raise ValueError("员工不存在")
    if employee.status != "active":
        raise ValueError("该员工已离职")

    existing = (
        db.query(SalaryRequest)
        .filter(
            SalaryRequest.employee_id == data.employee_id,
            SalaryRequest.month == data.month,
        )
        .first()
    )
    if existing:
        raise ValueError("该员工该月已有薪资申请")

    request = SalaryRequest(
        employee_id=data.employee_id,
        month=data.month,
        base_amount=data.base_amount,
        bonus_amount=data.bonus_amount,
        total_amount=round(data.base_amount + data.bonus_amount, 2),
        status="pending",
        requested_by=requested_by,
    )
    db.add(request)
    db.commit()
    db.refresh(request)
    return request


def get_salary_request(db: Session, request_id: int) -> SalaryRequest | None:
    return db.get(SalaryRequest, request_id)


def list_salary_requests(
    db: Session,
    employee_id: int | None = None,
    month: str | None = None,
    status: str | None = None,
) -> list[SalaryRequest]:
    query = db.query(SalaryRequest)
    if employee_id is not None:
        query = query.filter(SalaryRequest.employee_id == employee_id)
    if month is not None:
        query = query.filter(SalaryRequest.month == month)
    if status is not None:
        query = query.filter(SalaryRequest.status == status)
    return query.order_by(SalaryRequest.id).all()


def _review(db: Session, request_id: int, status: str, note: str, reviewed_by: str):
    request = get_salary_request(db, request_id)
    if not request:
        raise ValueError("薪资申请不存在")
    if request.status != "pending":
        raise ValueError("该薪资申请已处理")

    request.status = status
    request.review_note = note
    request.reviewed_at = datetime.now()
    request.reviewed_by = reviewed_by
    db.commit()
    db.refresh(request)
    return request


def approve_salary_request(
    db: Session, request_id: int, reviewed_by: str = ""
) -> SalaryRequest:
    """批准薪资申请：仅待审批可批准。"""
    return _review(db, request_id, "approved", "", reviewed_by)


def reject_salary_request(
    db: Session, request_id: int, note: str = "", reviewed_by: str = ""
) -> SalaryRequest:
    """驳回薪资申请：仅待审批可驳回，记录原因。"""
    return _review(db, request_id, "rejected", note, reviewed_by)


def create_shift(db: Session, data: ShiftCreate) -> StaffShift:
    """员工排班：在职员工、同员工同日唯一。"""
    employee = get_employee(db, data.employee_id)
    if not employee:
        raise ValueError("员工不存在")
    if employee.status != "active":
        raise ValueError("该员工已离职，不能排班")

    existing = (
        db.query(StaffShift)
        .filter(
            StaffShift.employee_id == data.employee_id,
            StaffShift.shift_date == data.shift_date,
        )
        .first()
    )
    if existing:
        raise ValueError("该员工当日已有排班")

    shift = StaffShift(
        employee_id=data.employee_id,
        shift_date=data.shift_date,
        shift_type=data.shift_type,
    )
    db.add(shift)
    db.commit()
    db.refresh(shift)
    return shift


def list_shifts(
    db: Session,
    employee_id: int | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[StaffShift]:
    query = db.query(StaffShift)
    if employee_id is not None:
        query = query.filter(StaffShift.employee_id == employee_id)
    if start_date is not None:
        query = query.filter(StaffShift.shift_date >= start_date)
    if end_date is not None:
        query = query.filter(StaffShift.shift_date <= end_date)
    return query.order_by(StaffShift.shift_date, StaffShift.id).all()


def delete_shift(db: Session, shift_id: int) -> None:
    """删除排班（排错更正）。"""
    shift = db.get(StaffShift, shift_id)
    if not shift:
        raise ValueError("排班记录不存在")
    db.delete(shift)
    db.commit()
