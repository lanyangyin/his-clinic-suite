from sqlalchemy.orm import Session
from .models import Patient
from .schemas import PatientCreate

def create_patient(db: Session, data: PatientCreate) -> Patient:
    """创建患者：如果身份证号已存在，返回已有记录；否则创建新记录。"""
    existing = db.query(Patient).filter(Patient.id_number == data.id_number).first()
    if existing:
        return existing

    patient = Patient(**data.model_dump())
    db.add(patient)
    db.commit()
    db.refresh(patient)
    return patient


def get_patient(db: Session, patient_id: int) -> Patient | None:
    """按 ID 查询患者；不存在时返回 None。"""
    return db.get(Patient, patient_id)


def get_patient_by_id_number(db: Session, id_number: str) -> Patient | None:
    """按身份证号查询患者（EMPI 查重）。"""
    return db.query(Patient).filter(Patient.id_number == id_number).first()


def list_patients(
    db: Session, name: str | None = None, id_number: str | None = None
) -> list[Patient]:
    """患者列表（可按姓名/身份证号过滤）。"""
    query = db.query(Patient)
    if name is not None:
        query = query.filter(Patient.name == name)
    if id_number is not None:
        query = query.filter(Patient.id_number == id_number)
    return query.order_by(Patient.id).all()