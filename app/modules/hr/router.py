from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.modules.auth.security import require_role

from .schemas import (
    AttendanceCreate,
    AttendanceResponse,
    AttendanceSummary,
    EmployeeCreate,
    EmployeeResponse,
    SalaryRequestCreate,
    SalaryRequestResponse,
    SalaryReviewRequest,
    ShiftCreate,
    ShiftResponse,
)
from .service import (
    approve_salary_request,
    attendance_summary,
    check_attendance,
    create_employee,
    create_salary_request,
    create_shift,
    delete_shift,
    get_employee,
    get_salary_request,
    list_attendance,
    list_employees,
    list_salary_requests,
    list_shifts,
    reject_salary_request,
    resign,
)

router = APIRouter(prefix="/hr", tags=["hr"])


@router.post("/employees/", response_model=EmployeeResponse, status_code=201)
def new_employee(
    data: EmployeeCreate,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("admin")),
):
    try:
        return create_employee(db, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/employees/", response_model=list[EmployeeResponse])
def get_all(
    status: str | None = None,
    department_id: int | None = None,
    db: Session = Depends(get_db),
):
    return list_employees(db, status, department_id)


@router.get("/employees/{employee_id}", response_model=EmployeeResponse)
def get_one(employee_id: int, db: Session = Depends(get_db)):
    employee = get_employee(db, employee_id)
    if not employee:
        raise HTTPException(status_code=404, detail="员工不存在")
    return employee


@router.post("/employees/{employee_id}/resign", response_model=EmployeeResponse)
def resign_employee(
    employee_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("admin")),
):
    try:
        return resign(db, employee_id)
    except ValueError as e:
        code = 404 if str(e) == "员工不存在" else 400
        raise HTTPException(status_code=code, detail=str(e))


@router.post("/attendance/check", response_model=AttendanceResponse, status_code=201)
def attendance_check(
    data: AttendanceCreate,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("admin")),
):
    try:
        return check_attendance(db, data)
    except ValueError as e:
        code = 404 if str(e) == "员工不存在" else 400
        raise HTTPException(status_code=code, detail=str(e))


@router.get("/attendance/", response_model=list[AttendanceResponse])
def get_attendance(
    employee_id: int | None = None,
    attendance_date: date | None = None,
    db: Session = Depends(get_db),
):
    return list_attendance(db, employee_id, attendance_date)


@router.get("/attendance/summary", response_model=AttendanceSummary)
def get_attendance_summary(
    employee_id: int, month: str, db: Session = Depends(get_db)
):
    try:
        return attendance_summary(db, employee_id, month)
    except (ValueError, IndexError):
        raise HTTPException(status_code=400, detail="月份格式应为 YYYY-MM")


@router.post("/salary-requests", response_model=SalaryRequestResponse, status_code=201)
def new_salary_request(
    data: SalaryRequestCreate,
    db: Session = Depends(get_db),
    user=Depends(require_role("admin")),
):
    try:
        return create_salary_request(db, data, user.username)
    except ValueError as e:
        code = 404 if str(e) == "员工不存在" else 400
        raise HTTPException(status_code=code, detail=str(e))


@router.get("/salary-requests", response_model=list[SalaryRequestResponse])
def get_salary_requests(
    employee_id: int | None = None,
    month: str | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
):
    return list_salary_requests(db, employee_id, month, status)


@router.get("/salary-requests/{request_id}", response_model=SalaryRequestResponse)
def get_salary_request_one(request_id: int, db: Session = Depends(get_db)):
    request = get_salary_request(db, request_id)
    if not request:
        raise HTTPException(status_code=404, detail="薪资申请不存在")
    return request


@router.post(
    "/salary-requests/{request_id}/approve", response_model=SalaryRequestResponse
)
def approve_salary(
    request_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_role("admin")),
):
    try:
        return approve_salary_request(db, request_id, user.username)
    except ValueError as e:
        code = 404 if str(e) == "薪资申请不存在" else 400
        raise HTTPException(status_code=code, detail=str(e))


@router.post(
    "/salary-requests/{request_id}/reject", response_model=SalaryRequestResponse
)
def reject_salary(
    request_id: int,
    data: SalaryReviewRequest,
    db: Session = Depends(get_db),
    user=Depends(require_role("admin")),
):
    try:
        return reject_salary_request(db, request_id, data.note, user.username)
    except ValueError as e:
        code = 404 if str(e) == "薪资申请不存在" else 400
        raise HTTPException(status_code=code, detail=str(e))


@router.post("/shifts", response_model=ShiftResponse, status_code=201)
def new_shift(
    data: ShiftCreate,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("admin")),
):
    try:
        return create_shift(db, data)
    except ValueError as e:
        code = 404 if str(e) == "员工不存在" else 400
        raise HTTPException(status_code=code, detail=str(e))


@router.get("/shifts", response_model=list[ShiftResponse])
def get_shifts(
    employee_id: int | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    db: Session = Depends(get_db),
):
    return list_shifts(db, employee_id, start_date, end_date)


@router.delete("/shifts/{shift_id}", status_code=204)
def remove_shift(
    shift_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("admin")),
):
    try:
        delete_shift(db, shift_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
