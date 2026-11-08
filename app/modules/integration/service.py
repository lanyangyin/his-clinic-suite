import re

from sqlalchemy.orm import Session

from app.modules.patient.schemas import PatientCreate
from app.modules.patient.service import (
    create_patient,
    get_patient,
    get_patient_by_id_number,
)

from .models import IntegrationLog


def log_integration(
    db: Session,
    protocol: str,
    direction: str,
    message_type: str,
    summary: str = "",
) -> IntegrationLog:
    log = IntegrationLog(
        protocol=protocol,
        direction=direction,
        message_type=message_type,
        summary=summary[:300],
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


def list_logs(db: Session, limit: int = 50) -> list[IntegrationLog]:
    return (
        db.query(IntegrationLog)
        .order_by(IntegrationLog.id.desc())
        .limit(limit)
        .all()
    )


def to_fhir_patient(patient) -> dict:
    """内部患者 → FHIR R4 Patient 资源。"""
    return {
        "resourceType": "Patient",
        "id": str(patient.id),
        "identifier": [
            {"system": "urn:oid:1.2.156.11201.idnum", "value": patient.id_number},
            {"system": "urn:oid:1.2.156.11201.empi", "value": str(patient.id)},
        ],
        "name": [{"family": patient.name, "given": [""]}],
        "telecom": (
            [{"system": "phone", "value": patient.phone}] if patient.phone else []
        ),
        "active": True,
    }


def parse_hl7_pid(message: str) -> tuple[str, str]:
    """解析 HL7 v2 ADT 消息的 PID 段，返回 (身份证号, 姓名)。

    支持格式（字段分隔符 |，组件分隔符 ^）：
    MSH|^~\\&|HIS|...
    PID|1||110101199001011234^张三||...
    """
    segments = [seg for seg in re.split(r"[\r\n]+", message.strip()) if seg]
    pid = next((seg for seg in segments if seg.startswith("PID")), None)
    if not pid:
        raise ValueError("消息缺少 PID 段")

    fields = pid.split("|")
    if len(fields) < 4:
        raise ValueError("PID 段格式不合法")
    components = fields[3].split("^")
    id_number = components[0].strip()
    name = components[1].strip() if len(components) > 1 else ""
    if not id_number:
        raise ValueError("PID 段缺少患者标识（身份证号）")
    return id_number, name


def handle_hl7_adt(db: Session, message: str) -> dict:
    """接收 HL7 ADT 消息：按身份证号幂等建档。"""
    id_number, name = parse_hl7_pid(message)
    existing = get_patient_by_id_number(db, id_number)
    patient = create_patient(
        db, PatientCreate(name=name or "未知", id_number=id_number)
    )
    created = existing is None
    log_integration(
        db,
        protocol="hl7",
        direction="in",
        message_type="ADT^A01",
        summary=f"PID 建档 id_number={id_number} patient_id={patient.id}",
    )
    return {"patient_id": patient.id, "created": created}
