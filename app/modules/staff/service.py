from sqlalchemy.orm import Session

from .models import Department, Doctor
from .schemas import DepartmentCreate, DoctorCreate


def create_department(db: Session, data: DepartmentCreate) -> Department:
    """创建科室：同名科室返回已有记录。"""
    existing = db.query(Department).filter(Department.name == data.name).first()
    if existing:
        return existing

    department = Department(name=data.name)
    db.add(department)
    db.commit()
    db.refresh(department)
    return department


def get_department(db: Session, department_id: int) -> Department | None:
    """按 ID 查询科室；不存在时返回 None。"""
    return db.get(Department, department_id)


def list_departments(db: Session) -> list[Department]:
    """全部科室（按 ID 排序）。"""
    return db.query(Department).order_by(Department.id).all()


def create_doctor(db: Session, data: DoctorCreate) -> Doctor:
    """创建医生：科室必须存在。"""
    department = get_department(db, data.department_id)
    if not department:
        raise ValueError("科室不存在")

    doctor = Doctor(name=data.name, department_id=data.department_id)
    db.add(doctor)
    db.commit()
    db.refresh(doctor)
    return doctor


def get_doctor(db: Session, doctor_id: int) -> Doctor | None:
    """按 ID 查询医生；不存在时返回 None。"""
    return db.get(Doctor, doctor_id)


def list_doctors(db: Session, department_id: int | None = None) -> list[Doctor]:
    """全部医生（可按科室过滤，按科室、id 排序）。"""
    query = db.query(Doctor)
    if department_id is not None:
        query = query.filter(Doctor.department_id == department_id)
    return query.order_by(Doctor.department_id, Doctor.id).all()
