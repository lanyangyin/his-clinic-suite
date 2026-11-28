from datetime import datetime

from sqlalchemy import true
from sqlalchemy.orm import Session

from app.modules.charges.service import add_charge
from app.modules.encounter.models import Encounter
from app.modules.encounter.service import get_medical_record, get_encounter

from .models import ImagingItem, ImagingReportTemplate, ImagingRequest
from .schemas import ImagingItemCreate, ImagingRequestCreate, ImagingTemplateCreate


def create_item(db: Session, data: ImagingItemCreate) -> ImagingItem:
    """维护影像检查项目字典：编码唯一。"""
    existing = db.query(ImagingItem).filter(ImagingItem.code == data.code).first()
    if existing:
        raise ValueError("检查项目编码已存在")

    item = ImagingItem(**data.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def create_template(db: Session, data: ImagingTemplateCreate) -> ImagingReportTemplate:
    if db.query(ImagingReportTemplate).filter(ImagingReportTemplate.name == data.name).first():
        raise ValueError("模板名称已存在")
    row = ImagingReportTemplate(**data.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def list_templates(db: Session, active_only: bool = True) -> list[ImagingReportTemplate]:
    query = db.query(ImagingReportTemplate)
    if active_only:
        query = query.filter(ImagingReportTemplate.active.is_(True))
    return query.order_by(ImagingReportTemplate.id).all()


def get_item(db: Session, item_id: int) -> ImagingItem | None:
    return db.get(ImagingItem, item_id)


def list_items(db: Session) -> list[ImagingItem]:
    """全部检查项目（按 ID 排序）。"""
    return db.query(ImagingItem).order_by(ImagingItem.id).all()


def create_request(
    db: Session, encounter_id: int, data: ImagingRequestCreate, requested_by: str = ""
) -> ImagingRequest:
    """医生开影像检查申请：就诊未关闭，项目必须存在。"""
    encounter = get_encounter(db, encounter_id)
    if not encounter:
        raise ValueError("就诊记录不存在")
    existing = (
        db.query(ImagingRequest)
        .filter(
            ImagingRequest.encounter_id == encounter.id,
            ImagingRequest.item_id == data.item_id,
            ImagingRequest.status.notin_(("cancelled", "rejected")),
        )
        .first()
    )
    if existing:
        raise ValueError("该检查项目已开立，请勿重复开单")
    if encounter.status == "closed":
        raise ValueError("就诊已关闭，不能开检查申请")
    if get_medical_record(db, encounter.id) and get_medical_record(db, encounter.id).signed_at:
        raise ValueError("病历已签名，不能再开检查；请先申请病历修订")
    if encounter.status == "abandoned":
        raise ValueError("就诊已放弃，不能开检查申请")

    if not get_item(db, data.item_id):
        raise ValueError("检查项目不存在")

    request = ImagingRequest(
        encounter_id=encounter_id,
        item_id=data.item_id,
        status="pending",
        priority=data.priority,
        requested_by=requested_by,
    )
    db.add(request)
    db.flush()

    # 计费：检查费（项目价格快照）
    # 0 元检查也保留费用行，允许完成 0 元收费并关闭就诊
    add_charge(
        db,
        encounter_id=encounter_id,
        source_type="imaging_request",
        source_id=request.id,
        charge_type="imaging",
        item_name=f"检查：{request.item.name}",
        quantity=1,
        unit_price=request.item.price,
        insurance_ratio=request.item.insurance_ratio,
    )

    db.commit()
    db.refresh(request)
    return request


def cancel_request(db: Session, request_id: int, operator: str = "") -> ImagingRequest:
    """取消尚未执行的影像检查申请；已收费必须先退费。"""
    request = get_request(db, request_id)
    if not request:
        raise ValueError("检查申请不存在")
    if request.status != "pending":
        raise ValueError("只有未执行的检查申请可以取消")
    from app.modules.charges.models import EncounterCharge

    charges = (
        db.query(EncounterCharge)
        .filter(
            EncounterCharge.source_type == "imaging_request",
            EncounterCharge.source_id == request.id,
        )
        .all()
    )
    if any(row.status in ("paid", "partially_refunded") for row in charges):
        request.status = "dc"
        db.commit()
        db.refresh(request)
        return request
    request.status = "cancelled"
    for row in charges:
        row.status = "cancelled"
    db.commit()
    db.refresh(request)
    return request


def get_request(db: Session, request_id: int) -> ImagingRequest | None:
    return db.get(ImagingRequest, request_id)


def list_requests(db: Session, encounter_id: int) -> list[ImagingRequest]:
    """就诊的全部影像检查申请（按申请顺序）。"""
    return (
        db.query(ImagingRequest)
        .filter(ImagingRequest.encounter_id == encounter_id)
        .order_by(ImagingRequest.id)
        .all()
    )


def report_request(
    db: Session,
    request_id: int,
    report: str = "",
    image_url: str = "",
    reported_by: str = "",
    findings: str = "",
    impression: str = "",
    template_name: str = "",
    study_uid: str = "",
    series_uid: str = "",
    modality: str = "",
    measurements: str = "",
) -> ImagingRequest:
    """影像科回传报告：仅 pending 可报告。"""
    request = get_request(db, request_id)
    if not request:
        raise ValueError("检查申请不存在")
    if request.status != "pending":
        raise ValueError("该检查申请已出报告")

    request.status = "reported"
    final_report = (report or "").strip() or "\n".join(
        part for part in ((findings or "").strip(), (impression or "").strip()) if part
    )
    if not final_report:
        raise ValueError("影像所见/诊断意见不能为空")
    request.report = final_report
    request.findings = (findings or report or "").strip()
    request.impression = (impression or "").strip()
    request.template_name = template_name
    request.image_url = image_url
    request.study_uid = study_uid
    request.series_uid = series_uid
    request.modality = modality
    request.measurements = measurements
    request.reported_at = datetime.now()
    request.reported_by = reported_by
    db.commit()
    db.refresh(request)

    _notify_result_ready(db, request.encounter_id)
    return request


def review_request(
    db: Session,
    request_id: int,
    approve: bool,
    reviewer: str,
    note: str = "",
) -> ImagingRequest:
    request = get_request(db, request_id)
    if not request:
        raise ValueError("检查申请不存在")
    if request.status != "reported":
        raise ValueError("仅已报告检查可以审核")
    if not approve and not note.strip():
        raise ValueError("退回报告必须填写原因")
    request.status = "reviewed" if approve else "rejected"
    request.reviewed_by = reviewer
    request.reviewed_at = datetime.now()
    request.review_note = note
    db.commit()
    db.refresh(request)
    return request


def _notify_result_ready(db: Session, encounter_id: int) -> None:
    """检查报告出结果短信通知（Mock 网关，患者有手机号才发）。"""
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
            content="您的检查报告已出，请到自助机或服务台打印。",
            template="report_ready",
        )


def list_worklist(db: Session, status: str = "pending", priority: str | None = None) -> list[dict]:
    from app.modules.patient.models import Patient
    from app.modules.registration.models import Registration

    from app.modules.billing.models import Payment

    from app.modules.charges.models import EncounterCharge

    history_only = status in ("reported", "reviewed", "rejected")
    query = (
        db.query(ImagingRequest, Patient)
        .join(Encounter, ImagingRequest.encounter_id == Encounter.id)
        .join(Registration, Encounter.registration_id == Registration.id)
        .join(Patient, Registration.patient_id == Patient.id)
    )
    if not history_only:
        paid_requests = db.query(EncounterCharge.source_id).filter(
            EncounterCharge.source_type == "imaging_request",
            EncounterCharge.status.in_(("paid", "partially_refunded")),
        )
        query = query.filter(ImagingRequest.id.in_(paid_requests))
    if status:
        query = query.filter(ImagingRequest.status == status)
    else:
        query = query.filter(ImagingRequest.status.notin_(("cancelled", "dc")))
    if priority:
        query = query.filter(ImagingRequest.priority == priority)
    rows = query.order_by(
        (ImagingRequest.priority == "routine").asc(),
        ImagingRequest.requested_at.asc(),
        ImagingRequest.id.asc(),
    ).all()
    return [
        {
            "id": request.id,
            "encounter_id": request.encounter_id,
            "accession_no": request.accession_no,
            "item_name": request.item_name,
            "patient_name": patient.name,
            "patient_no": patient.patient_no,
            "gender": patient.gender,
            "age": patient.age,
            "requested_by": request.requested_by,
            "requested_at": request.requested_at,
            "status": request.status,
            "priority": request.priority,
            "report": request.report,
            "reported_by": request.reported_by,
            "reviewed_by": request.reviewed_by,
        }
        for request, patient in rows
    ]
