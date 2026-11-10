from datetime import datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .models import Patient
from .schemas import DuplicateCandidate, PatientCreate, PatientUpdate


def _derive_from_id(id_type: str, id_number: str | None):
    """身份证可带出出生日期和性别；其他证件不猜。"""
    if id_type != "id_card" or not id_number:
        return None, None
    digits = id_number.strip()
    if len(digits) != 18 or not digits[:17].isdigit():
        return None, None
    try:
        birth = datetime.strptime(digits[6:14], "%Y%m%d").date()
    except ValueError:
        return None, None
    gender = "male" if int(digits[16]) % 2 else "female"
    return birth, gender


def _apply_identity(patient: Patient) -> None:
    birth, gender = _derive_from_id(patient.id_type, patient.id_number)
    if patient.birth_date is None and birth is not None:
        patient.birth_date = birth
    if patient.gender in (None, "", "unknown") and gender:
        patient.gender = gender


def create_patient(db: Session, data: PatientCreate, operator: str = "") -> Patient:
    """创建患者。证件号已存在时返回已有记录（兼容旧接口，UI 会先查重）。"""
    if data.id_number:
        existing = (
            db.query(Patient).filter(Patient.id_number == data.id_number).first()
        )
        if existing:
            return existing

    payload = data.model_dump(exclude={"privacy_consent"})
    if payload["id_type"] == "none":
        payload["id_number"] = None
    patient = Patient(**payload)
    patient.created_by = operator
    patient.updated_by = operator
    if data.privacy_consent:
        patient.privacy_consent_at = datetime.now()
    _apply_identity(patient)
    db.add(patient)
    try:
        db.flush()
        patient.patient_no = f"P{patient.id:08d}"
        db.commit()
    except IntegrityError:
        db.rollback()
        if data.id_number:
            existing = (
                db.query(Patient).filter(Patient.id_number == data.id_number).first()
            )
            if existing:
                return existing
        raise
    db.refresh(patient)
    return patient


def update_patient(
    db: Session, patient_id: int, data: PatientUpdate, operator: str = ""
) -> Patient | None:
    patient = db.get(Patient, patient_id)
    if not patient:
        return None
    values = data.model_dump(exclude_unset=True, exclude={"privacy_consent"})
    if "id_number" in values:
        values["id_number"] = (values["id_number"] or "").strip() or None
        if values["id_number"] and values["id_number"] != patient.id_number:
            duplicate = (
                db.query(Patient)
                .filter(
                    Patient.id_number == values["id_number"],
                    Patient.id != patient_id,
                )
                .first()
            )
            if duplicate:
                raise ValueError(f"证件号已被患者 {duplicate.patient_no or duplicate.id} 使用")
    if "id_type" in values and values["id_type"] == "none":
        values["id_number"] = None
    for key, value in values.items():
        setattr(patient, key, value)
    if data.privacy_consent and patient.privacy_consent_at is None:
        patient.privacy_consent_at = datetime.now()
    if patient.allergy_status != "present":
        patient.allergy_detail = ""
    patient.updated_by = operator
    patient.updated_at = datetime.now()
    _apply_identity(patient)
    db.commit()
    db.refresh(patient)
    return patient


def get_patient(db: Session, patient_id: int) -> Patient | None:
    return db.get(Patient, patient_id)


def get_patient_by_id_number(db: Session, id_number: str | None) -> Patient | None:
    if not id_number:
        return None
    return db.query(Patient).filter(Patient.id_number == id_number).first()


def list_patients(
    db: Session,
    name: str | None = None,
    id_number: str | None = None,
    phone: str | None = None,
) -> list[Patient]:
    query = db.query(Patient)
    if name is not None:
        query = query.filter(Patient.name == name)
    if id_number is not None:
        query = query.filter(Patient.id_number == id_number)
    if phone is not None:
        query = query.filter(Patient.phone == phone)
    return query.order_by(Patient.id).all()


def find_duplicates(
    db: Session, name: str = "", id_number: str = "", phone: str = ""
) -> tuple[bool, list[DuplicateCandidate]]:
    """建档查重：证件号精确命中优先；否则按姓名+电话给候选。"""
    name = (name or "").strip()
    id_number = (id_number or "").strip()
    phone = (phone or "").strip()
    exact_patient = None
    if id_number:
        exact_patient = (
            db.query(Patient).filter(Patient.id_number == id_number).first()
        )
    if exact_patient:
        return True, [
            DuplicateCandidate(
                id=exact_patient.id,
                patient_no=exact_patient.patient_no,
                name=exact_patient.name,
                gender=exact_patient.gender,
                birth_date=exact_patient.birth_date,
                phone=exact_patient.phone,
                id_number=exact_patient.id_number,
                exact=True,
            )
        ]

    query = db.query(Patient).filter(Patient.status == "normal")
    if name and phone:
        query = query.filter(Patient.name == name, Patient.phone == phone)
    elif name:
        query = query.filter(Patient.name == name)
    elif phone:
        query = query.filter(Patient.phone == phone)
    else:
        return False, []
    rows = query.order_by(Patient.id.desc()).limit(10).all()
    return False, [
        DuplicateCandidate(
            id=row.id,
            patient_no=row.patient_no,
            name=row.name,
            gender=row.gender,
            birth_date=row.birth_date,
            phone=row.phone,
            id_number=row.id_number,
            exact=False,
        )
        for row in rows
    ]
