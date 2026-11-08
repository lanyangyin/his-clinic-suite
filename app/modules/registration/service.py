from datetime import date

from sqlalchemy.orm import Session

from app.modules.patient.service import get_patient
from app.modules.staff.service import get_doctor

from .models import DoctorSchedule, Registration
from .schemas import RegistrationCreate, ScheduleCreate


def create_schedule(db: Session, data: ScheduleCreate) -> DoctorSchedule:
    """建立排班（号源）：医生存在，且同日同段不重复。"""
    if not get_doctor(db, data.doctor_id):
        raise ValueError("医生不存在")

    if data.room_id is not None:
        from app.modules.facility.service import get_room

        if not get_room(db, data.room_id):
            raise ValueError("诊室不存在")

    existing = (
        db.query(DoctorSchedule)
        .filter(
            DoctorSchedule.doctor_id == data.doctor_id,
            DoctorSchedule.schedule_date == data.schedule_date,
            DoctorSchedule.period == data.period,
        )
        .first()
    )
    if existing:
        raise ValueError("该医生该时段已有排班")

    schedule = DoctorSchedule(
        doctor_id=data.doctor_id,
        schedule_date=data.schedule_date,
        period=data.period,
        capacity=data.capacity,
        booked=0,
        room_id=data.room_id,
    )
    db.add(schedule)
    db.commit()
    db.refresh(schedule)
    return schedule


def get_schedule(db: Session, schedule_id: int) -> DoctorSchedule | None:
    return db.get(DoctorSchedule, schedule_id)


def list_schedules(
    db: Session, doctor_id: int, schedule_date: date | None = None
) -> list[DoctorSchedule]:
    """医生的排班列表（可按日期过滤）。"""
    query = db.query(DoctorSchedule).filter(DoctorSchedule.doctor_id == doctor_id)
    if schedule_date is not None:
        query = query.filter(DoctorSchedule.schedule_date == schedule_date)
    return query.order_by(DoctorSchedule.schedule_date, DoctorSchedule.period).all()


def take_schedule_slot(db: Session, schedule_id: int, doctor_id: int) -> None:
    """原子占号：仅当有剩余号源时 booked+1。

    用条件 UPDATE（booked < capacity）代替"读-改-写"，并发下不会超卖。
    """
    schedule = get_schedule(db, schedule_id)
    if not schedule:
        raise ValueError("排班不存在")
    if schedule.doctor_id != doctor_id:
        raise ValueError("排班与医生不匹配")

    affected = (
        db.query(DoctorSchedule)
        .filter(
            DoctorSchedule.id == schedule_id,
            DoctorSchedule.booked < DoctorSchedule.capacity,
        )
        .update(
            {DoctorSchedule.booked: DoctorSchedule.booked + 1},
            synchronize_session=False,
        )
    )
    if affected != 1:
        raise ValueError("该时段号源已满")


def release_schedule_slot(db: Session, schedule_id: int) -> None:
    """释放号源（爽约/取消预约）：booked 减 1，不低于 0。"""
    db.query(DoctorSchedule).filter(
        DoctorSchedule.id == schedule_id, DoctorSchedule.booked > 0
    ).update(
        {DoctorSchedule.booked: DoctorSchedule.booked - 1},
        synchronize_session=False,
    )


def create_registration_for_appointment(
    db: Session, patient_id: int, doctor_id: int, schedule_id: int
) -> Registration:
    """预约取号：号源在预约时已占用，这里直接生成挂号记录（不再占号）。"""
    registration = Registration(
        patient_id=patient_id,
        doctor_id=doctor_id,
        schedule_id=schedule_id,
    )
    db.add(registration)
    db.flush()
    return registration


def create_registration(db: Session, data: RegistrationCreate) -> Registration:
    """挂号：确认患者和医生都存在；指定排班时校验号源并占用。"""
    patient = get_patient(db, data.patient_id)
    if not patient:
        raise ValueError("患者不存在")

    doctor = get_doctor(db, data.doctor_id)
    if not doctor:
        raise ValueError("医生不存在")

    if data.schedule_id is not None:
        take_schedule_slot(db, data.schedule_id, data.doctor_id)

    registration = Registration(
        patient_id=data.patient_id,
        doctor_id=data.doctor_id,
        schedule_id=data.schedule_id,
    )
    db.add(registration)
    db.commit()
    db.refresh(registration)
    return registration


def get_registration(db: Session, registration_id: int) -> Registration | None:
    """按 ID 查询挂号记录；不存在时返回 None。"""
    return db.get(Registration, registration_id)


def list_registrations(
    db: Session,
    patient_id: int | None = None,
    doctor_id: int | None = None,
    status: str | None = None,
) -> list[Registration]:
    """挂号列表（可按患者/医生/状态过滤，最新在前）。"""
    query = db.query(Registration)
    if patient_id is not None:
        query = query.filter(Registration.patient_id == patient_id)
    if doctor_id is not None:
        query = query.filter(Registration.doctor_id == doctor_id)
    if status is not None:
        query = query.filter(Registration.status == status)
    return query.order_by(Registration.id.desc()).all()


def get_patient_registration_ids(db: Session, patient_id: int) -> list[int]:
    """患者的全部挂号 ID（供其他模块按患者查询就诊）。"""
    rows = (
        db.query(Registration.id)
        .filter(Registration.patient_id == patient_id)
        .all()
    )
    return [row[0] for row in rows]


def mark_registration_visited(db: Session, registration: Registration) -> None:
    """把挂号状态改为 visited（只改内存，由调用方统一 commit）。"""
    registration.status = "visited"
