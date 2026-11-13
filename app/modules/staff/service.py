from sqlalchemy.orm import Session

from .models import Department, Doctor
from .schemas import DepartmentCreate, DoctorCreate


def create_department(db: Session, data: DepartmentCreate) -> Department:
    """创建科室：同名科室返回已有记录。"""
    existing = db.query(Department).filter(Department.name == data.name).first()
    if existing:
        if not existing.active:
            existing.active = True
            db.commit()
            db.refresh(existing)
        return existing

    department = Department(name=data.name)
    db.add(department)
    db.commit()
    db.refresh(department)
    return department


def get_department(db: Session, department_id: int) -> Department | None:
    """按 ID 查询科室；不存在时返回 None。"""
    return db.get(Department, department_id)


def list_departments(
    db: Session, include_inactive: bool = False
) -> list[Department]:
    """科室；默认只返回启用科室。"""
    query = db.query(Department)
    if not include_inactive:
        query = query.filter(Department.active.is_(True))
    return query.order_by(Department.id).all()


def deactivate_department(db: Session, department_id: int) -> Department:
    department = get_department(db, department_id)
    if not department:
        raise ValueError("科室不存在")
    active_doctor = (
        db.query(Doctor)
        .filter(Doctor.department_id == department_id, Doctor.active.is_(True))
        .first()
    )
    if active_doctor:
        raise ValueError("科室仍有在职医生，请先停用/转出医生")
    department.active = False
    db.commit()
    db.refresh(department)
    return department


def create_doctor(db: Session, data: DoctorCreate) -> Doctor:
    """创建医生：科室必须存在。"""
    department = get_department(db, data.department_id)
    if not department:
        raise ValueError("科室不存在")
    if not department.active:
        raise ValueError("科室已停用")

    doctor = Doctor(name=data.name, department_id=data.department_id)
    db.add(doctor)
    db.commit()
    db.refresh(doctor)
    return doctor


def get_doctor(db: Session, doctor_id: int) -> Doctor | None:
    """按 ID 查询医生；不存在时返回 None。"""
    return db.get(Doctor, doctor_id)


def list_doctors(
    db: Session,
    department_id: int | None = None,
    include_inactive: bool = False,
) -> list[Doctor]:
    """医生；默认只返回未停用医生。"""
    query = db.query(Doctor)
    if not include_inactive:
        query = query.filter(Doctor.active.is_(True))
    if department_id is not None:
        query = query.filter(Doctor.department_id == department_id)
    return query.order_by(Doctor.department_id, Doctor.id).all()


def deactivate_doctor(db: Session, doctor_id: int) -> Doctor:
    doctor = get_doctor(db, doctor_id)
    if not doctor:
        raise ValueError("医生不存在")
    if doctor.current_encounter_id:
        from app.modules.encounter.models import Encounter

        encounter = db.get(Encounter, doctor.current_encounter_id)
        if encounter and encounter.status in ("open", "paused"):
            raise ValueError("医生还有未完成就诊，不能停用")
    doctor.active = False
    db.commit()
    db.refresh(doctor)
    return doctor
