from datetime import datetime

from sqlalchemy.orm import Session

from app.modules.charges.service import add_charge
from app.modules.encounter.models import Encounter
from app.modules.encounter.service import get_encounter
from app.modules.patient.models import Patient
from app.modules.registration.models import Registration
from app.modules.staff.models import Doctor

from .models import LabItem, LabRequest
from .schemas import (
    CriticalRequest,
    LabItemCreate,
    LabReportRequest,
    LabRequestCreate,
    RejectRequest,
    SpecimenActionRequest,
)

REPORTABLE = {"pending", "collected", "received", "testing"}


def create_item(db: Session, data: LabItemCreate) -> LabItem:
    """维护检验项目字典：编码唯一。"""
    existing = db.query(LabItem).filter(LabItem.code == data.code).first()
    if existing:
        raise ValueError("检验项目编码已存在")
    item = LabItem(**data.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def get_item(db: Session, item_id: int) -> LabItem | None:
    return db.get(LabItem, item_id)


def list_items(db: Session) -> list[LabItem]:
    return db.query(LabItem).order_by(LabItem.id).all()


def create_request(
    db: Session,
    encounter_id: int,
    data: LabRequestCreate,
    requested_by: str = "",
) -> LabRequest:
    """医生开检验申请：生成标本号，等待护士采样/检验科签收。"""
    encounter = get_encounter(db, encounter_id)
    if not encounter:
        raise ValueError("就诊记录不存在")
    if encounter.status == "closed":
        raise ValueError("就诊已关闭，不能开检验申请")

    item = get_item(db, data.item_id)
    if not item:
        raise ValueError("检验项目不存在")

    request = LabRequest(
        encounter_id=encounter_id,
        item_id=data.item_id,
        status="pending",
        priority=data.priority,
        specimen_type=item.specimen_type,
        requested_by=requested_by,
    )
    db.add(request)
    db.flush()
    request.specimen_no = f"LAB{datetime.now():%Y%m%d}{request.id:05d}"

    if item.price > 0:
        add_charge(
            db,
            encounter_id=encounter_id,
            source_type="lab_request",
            source_id=request.id,
            charge_type="lab",
            item_name=f"检验：{item.name}",
            quantity=1,
            unit_price=item.price,
            insurance_ratio=item.insurance_ratio,
        )

    db.commit()
    db.refresh(request)
    return request


def get_request(db: Session, request_id: int) -> LabRequest | None:
    return db.get(LabRequest, request_id)


def list_requests(db: Session, encounter_id: int) -> list[LabRequest]:
    return (
        db.query(LabRequest)
        .filter(LabRequest.encounter_id == encounter_id)
        .order_by(LabRequest.id)
        .all()
    )


def collect_request(
    db: Session, request_id: int, data: SpecimenActionRequest, operator: str = ""
) -> LabRequest:
    """护士采样：待采样/被拒收的标本可重新采样。"""
    request = get_request(db, request_id)
    if not request:
        raise ValueError("检验申请不存在")
    if request.status not in ("pending", "rejected"):
        raise ValueError("该检验申请当前状态不可采样")
    request.status = "collected"
    request.collected_at = datetime.now()
    request.collected_by = operator
    request.reject_reason = None
    request.specimen_no = request.specimen_no or f"LAB{datetime.now():%Y%m%d}{request.id:05d}"
    if data.note:
        request.reject_reason = None
    db.commit()
    db.refresh(request)
    return request


def receive_request(db: Session, request_id: int, operator: str = "") -> LabRequest:
    """检验科签收标本。"""
    request = get_request(db, request_id)
    if not request:
        raise ValueError("检验申请不存在")
    if request.status != "collected":
        raise ValueError("标本未采样，不能签收")
    request.status = "received"
    request.received_at = datetime.now()
    request.received_by = operator
    db.commit()
    db.refresh(request)
    return request


def reject_request(
    db: Session, request_id: int, data: RejectRequest, operator: str = ""
) -> LabRequest:
    """标本拒收（溶血/凝块/量不足等），退回护士重采。"""
    request = get_request(db, request_id)
    if not request:
        raise ValueError("检验申请不存在")
    if request.status not in ("collected", "received"):
        raise ValueError("该标本当前状态不可拒收")
    request.status = "rejected"
    request.reject_reason = data.reason
    request.received_by = operator
    db.commit()
    db.refresh(request)
    return request


def start_testing(db: Session, request_id: int, operator: str = "") -> LabRequest:
    request = get_request(db, request_id)
    if not request:
        raise ValueError("检验申请不存在")
    if request.status != "received":
        raise ValueError("标本未签收，不能开始检验")
    request.status = "testing"
    request.testing_at = datetime.now()
    request.testing_by = operator
    db.commit()
    db.refresh(request)
    return request


def report_request(
    db: Session, request_id: int, data: LabReportRequest | str
) -> LabRequest:
    """检验科出结果：支持结构化数值/文本；旧接口只传文本仍兼容。"""
    if isinstance(data, str):
        data = LabReportRequest(result=data)
    request = get_request(db, request_id)
    if not request:
        raise ValueError("检验申请不存在")
    if request.status in ("reported", "reviewed"):
        raise ValueError("该检验申请已出结果")
    if request.status not in REPORTABLE:
        raise ValueError("该检验申请当前状态不可报告")

    flag = data.abnormal_flag
    low = data.reference_low if data.reference_low is not None else request.item.reference_low
    high = data.reference_high if data.reference_high is not None else request.item.reference_high
    if data.result_value is not None and not flag:
        if low is not None and data.result_value < low:
            flag = "L"
        elif high is not None and data.result_value > high:
            flag = "H"
        else:
            flag = "N"

    text = data.result.strip()
    if not text and data.result_value is not None:
        text = f"{data.result_value:g} {data.result_unit or request.item.unit}".strip()

    request.status = "reported"
    request.result = text
    request.result_value = data.result_value
    request.result_unit = data.result_unit or request.item.unit
    request.reference_low = low
    request.reference_high = high
    request.abnormal_flag = flag
    request.critical_flag = data.critical_flag
    request.critical_note = data.critical_note or None
    request.critical_notified_to = data.critical_notified_to or None
    request.critical_notified_at = datetime.now() if data.critical_notified_to else None
    request.reported_at = datetime.now()
    request.report_no = request.report_no or f"RPT{datetime.now():%Y%m%d}{request.id:05d}"
    db.commit()
    db.refresh(request)

    _notify_result_ready(db, request.encounter_id, "检验")
    return request


def review_request(db: Session, request_id: int, operator: str = "") -> LabRequest:
    """报告审核：审核后才算最终报告。"""
    request = get_request(db, request_id)
    if not request:
        raise ValueError("检验申请不存在")
    if request.status != "reported":
        raise ValueError("报告未出具，不能审核")
    if request.critical_flag and not request.critical_notified_to:
        raise ValueError("危急值尚未登记通知对象，不能审核")
    request.status = "reviewed"
    request.reviewed_at = datetime.now()
    request.reviewed_by = operator
    db.commit()
    db.refresh(request)
    return request


def register_critical(    db: Session, request_id: int, data: CriticalRequest, operator: str = ""
) -> LabRequest:
    request = get_request(db, request_id)
    if not request:
        raise ValueError("检验申请不存在")
    if request.status not in ("reported", "reviewed"):
        raise ValueError("报告未出具，不能登记危急值")
    request.critical_flag = True
    request.critical_note = data.note
    request.critical_notified_to = data.notified_to
    request.critical_notified_at = datetime.now() if data.notified_to else None
    if operator and not request.reviewed_by:
        request.testing_by = request.testing_by or operator
    db.commit()
    db.refresh(request)
    return request


def acknowledge_critical(
    db: Session, request_id: int, note: str = "", operator: str = ""
) -> LabRequest:
    """医生确认危急值：必须有通知对象，记录确认人/时间/备注。"""
    request = get_request(db, request_id)
    if not request:
        raise ValueError("检验申请不存在")
    if not request.critical_flag:
        raise ValueError("该报告不是危急值")
    if request.critical_ack_at:
        raise ValueError("该危急值已确认，不能重复确认")
    if not request.critical_notified_to:
        raise ValueError("危急值尚未登记通知对象，不能确认")
    request.critical_ack_by = operator
    request.critical_ack_at = datetime.now()
    request.critical_ack_note = note or None
    db.commit()
    db.refresh(request)
    return request


def critical_alerts(db: Session) -> list[dict]:
    """医生工作台：未确认的危急值，按报告时间倒序。"""
    rows = [
        row
        for row in worklist(db)
        if row["critical_pending"] and row["status"] in ("reported", "reviewed")
    ]
    return rows


def worklist(
    db: Session,
    status: str | None = None,
    priority: str | None = None,
) -> list[dict]:
    """检验科工作列表：带患者/就诊/标本/结果信息。"""
    query = (
        db.query(LabRequest, Patient)
        .join(Encounter, LabRequest.encounter_id == Encounter.id)
        .join(Registration, Encounter.registration_id == Registration.id)
        .join(Patient, Registration.patient_id == Patient.id)
    )
    if status:
        statuses = [item.strip() for item in status.split(",") if item.strip()]
        if statuses:
            query = query.filter(LabRequest.status.in_(statuses))
    if priority:
        query = query.filter(LabRequest.priority == priority)
    rows = query.order_by(LabRequest.id.desc()).all()
    result = []
    for request, patient in rows:
        encounter = get_encounter(db, request.encounter_id)
        registration = db.get(Registration, encounter.registration_id) if encounter else None
        doctor = db.get(Doctor, registration.doctor_id) if registration else None
        result.append(
            {
                "id": request.id,
                "encounter_id": request.encounter_id,
                "patient_id": patient.id,
                "patient_name": patient.name,
                "patient_phone": patient.phone,
                "doctor_name": doctor.name if doctor else "",
                "diagnosis": encounter.diagnosis if encounter else "",
                "item_id": request.item_id,
                "item_name": request.item_name,
                "specimen_type": request.specimen_type,
                "specimen_no": request.specimen_no,
                "status": request.status,
                "priority": request.priority,
                "requested_at": request.requested_at,
                "collected_at": request.collected_at,
                "received_at": request.received_at,
                "reported_at": request.reported_at,
                "report_no": request.report_no,
                "reviewed_at": request.reviewed_at,
                "reviewed_by": request.reviewed_by,
                "result_display": request.result_display,
                "abnormal_flag": request.abnormal_flag,
                "critical_flag": request.critical_flag,
                "critical_notified_to": request.critical_notified_to,
                "critical_notified_at": request.critical_notified_at,
                "critical_ack_by": request.critical_ack_by,
                "critical_ack_at": request.critical_ack_at,
                "critical_ack_note": request.critical_ack_note,
                "critical_pending": request.critical_pending,
                "critical_age_minutes": request.critical_age_minutes,
                "critical_overdue": request.critical_overdue,
                "result_unit": request.result_unit,
                "reference_low": request.reference_low,
                "reference_high": request.reference_high,
            }
        )
    return result


def _notify_result_ready(db: Session, encounter_id: int, kind: str) -> None:
    """报告出结果短信通知（Mock 网关，患者有手机号才发）。"""
    from app.modules.patient.service import get_patient
    from app.modules.registration.service import get_registration
    from app.modules.sms.service import send_sms

    encounter = get_encounter(db, encounter_id)
    if not encounter:
        return
    registration = get_registration(db, encounter.registration_id)
    if not registration:
        return
    patient = get_patient(db, registration.patient_id)
    if patient and patient.phone:
        send_sms(
            db,
            phone=patient.phone,
            content=f"您的{kind}报告已出，请到自助机或服务台打印。",
            template="report_ready",
        )
