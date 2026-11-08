from datetime import date, datetime

from sqlalchemy.orm import Session

from app.modules.patient.service import get_patient
from app.modules.registration.service import (
    create_registration_for_appointment,
    get_schedule,
    release_schedule_slot,
    take_schedule_slot,
)
from app.modules.sms.service import send_sms
from app.modules.staff.service import get_doctor

from .models import Appointment
from .schemas import AppointmentCreate


def create_appointment(
    db: Session, data: AppointmentCreate, created_by: str = ""
) -> Appointment:
    """预约挂号：校验患者/医生/排班，占号后落预约单（同一排班不可重复预约）。"""
    patient = get_patient(db, data.patient_id)
    if not patient:
        raise ValueError("患者不存在")
    doctor = get_doctor(db, data.doctor_id)
    if not doctor:
        raise ValueError("医生不存在")

    schedule = get_schedule(db, data.schedule_id)
    if not schedule:
        raise ValueError("排班不存在")
    if schedule.doctor_id != data.doctor_id:
        raise ValueError("排班与医生不匹配")
    if schedule.schedule_date < date.today():
        raise ValueError("排班日期已过")

    existing = (
        db.query(Appointment)
        .filter(
            Appointment.patient_id == data.patient_id,
            Appointment.schedule_id == data.schedule_id,
            Appointment.status.in_(("booked", "checked_in")),
        )
        .first()
    )
    if existing:
        raise ValueError("该患者已预约此排班")

    # 占号（原子条件更新，已满则报错）
    take_schedule_slot(db, schedule.id, data.doctor_id)

    appointment = Appointment(
        patient_id=data.patient_id,
        doctor_id=data.doctor_id,
        schedule_id=data.schedule_id,
        status="booked",
        created_by=created_by,
    )
    db.add(appointment)
    db.commit()
    db.refresh(appointment)

    if patient.phone:
        send_sms(
            db,
            phone=patient.phone,
            content=(
                f"预约成功：{doctor.name} {schedule.schedule_date} "
                f"{'上午' if schedule.period == 'morning' else '下午'}，请按时就诊。"
            ),
            template="appointment",
        )
    return appointment


def get_appointment(db: Session, appointment_id: int) -> Appointment | None:
    return db.get(Appointment, appointment_id)


def list_appointments(
    db: Session,
    patient_id: int | None = None,
    doctor_id: int | None = None,
    status: str | None = None,
) -> list[Appointment]:
    query = db.query(Appointment)
    if patient_id is not None:
        query = query.filter(Appointment.patient_id == patient_id)
    if doctor_id is not None:
        query = query.filter(Appointment.doctor_id == doctor_id)
    if status is not None:
        query = query.filter(Appointment.status == status)
    return query.order_by(Appointment.id.desc()).all()


def check_in(db: Session, appointment_id: int) -> Appointment:
    """取号：booked → checked_in，并生成正式挂号记录（号源预约时已占用）。"""
    appointment = get_appointment(db, appointment_id)
    if not appointment:
        raise ValueError("预约不存在")
    if appointment.status != "booked":
        raise ValueError("该预约状态不可取号")

    affected = (
        db.query(Appointment)
        .filter(
            Appointment.id == appointment_id,
            Appointment.status == "booked",
        )
        .update(
            {
                Appointment.status: "checked_in",
                Appointment.checked_in_at: datetime.now(),
            },
            synchronize_session=False,
        )
    )
    if affected != 1:
        raise ValueError("该预约状态不可取号")

    registration = create_registration_for_appointment(
        db,
        patient_id=appointment.patient_id,
        doctor_id=appointment.doctor_id,
        schedule_id=appointment.schedule_id,
    )
    appointment.registration_id = registration.id
    db.commit()
    db.refresh(appointment)
    return appointment


def no_show(db: Session, appointment_id: int) -> Appointment:
    """爽约：释放号源，状态置 no_show。"""
    appointment = get_appointment(db, appointment_id)
    if not appointment:
        raise ValueError("预约不存在")
    if appointment.status != "booked":
        raise ValueError("仅已预约状态可标记爽约")

    affected = (
        db.query(Appointment)
        .filter(Appointment.id == appointment_id, Appointment.status == "booked")
        .update({Appointment.status: "no_show"}, synchronize_session=False)
    )
    if affected != 1:
        raise ValueError("仅已预约状态可标记爽约")

    release_schedule_slot(db, appointment.schedule_id)
    db.commit()
    db.refresh(appointment)
    return appointment


def cancel(db: Session, appointment_id: int) -> Appointment:
    """取消预约：释放号源，状态置 cancelled。"""
    appointment = get_appointment(db, appointment_id)
    if not appointment:
        raise ValueError("预约不存在")
    if appointment.status != "booked":
        raise ValueError("仅已预约状态可取消")

    affected = (
        db.query(Appointment)
        .filter(Appointment.id == appointment_id, Appointment.status == "booked")
        .update({Appointment.status: "cancelled"}, synchronize_session=False)
    )
    if affected != 1:
        raise ValueError("仅已预约状态可取消")

    release_schedule_slot(db, appointment.schedule_id)
    db.commit()
    db.refresh(appointment)
    return appointment
