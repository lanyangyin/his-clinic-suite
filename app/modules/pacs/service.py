from datetime import datetime

from sqlalchemy.orm import Session

from app.modules.charges.service import add_charge
from app.modules.encounter.service import get_encounter

from .models import ImagingItem, ImagingRequest
from .schemas import ImagingItemCreate, ImagingRequestCreate


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
    if encounter.status == "closed":
        raise ValueError("就诊已关闭，不能开检查申请")

    if not get_item(db, data.item_id):
        raise ValueError("检查项目不存在")

    request = ImagingRequest(
        encounter_id=encounter_id,
        item_id=data.item_id,
        status="pending",
        requested_by=requested_by,
    )
    db.add(request)
    db.flush()

    # 计费：检查费（项目价格快照）
    if request.item.price > 0:
        add_charge(
            db,
            encounter_id=encounter_id,
            source_type="imaging_request",
            source_id=request.id,
            charge_type="imaging",
            item_name=f"检查：{request.item.name}",
            quantity=1,
            unit_price=request.item.price,
            insurance_ratio=0.7,
        )

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
    db: Session, request_id: int, report: str, image_url: str = ""
) -> ImagingRequest:
    """影像科回传报告：仅 pending 可报告。"""
    request = get_request(db, request_id)
    if not request:
        raise ValueError("检查申请不存在")
    if request.status != "pending":
        raise ValueError("该检查申请已出报告")

    request.status = "reported"
    request.report = report
    request.image_url = image_url
    request.reported_at = datetime.now()
    db.commit()
    db.refresh(request)

    _notify_result_ready(db, request.encounter_id)
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
