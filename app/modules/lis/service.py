from datetime import datetime

from sqlalchemy.orm import Session

from app.modules.charges.service import add_charge
from app.modules.encounter.service import get_encounter

from .models import LabItem, LabRequest
from .schemas import LabItemCreate, LabRequestCreate


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
    """全部检验项目（按 ID 排序）。"""
    return db.query(LabItem).order_by(LabItem.id).all()


def create_request(
    db: Session, encounter_id: int, data: LabRequestCreate, requested_by: str = ""
) -> LabRequest:
    """医生开检验申请：就诊未关闭，项目必须存在。"""
    encounter = get_encounter(db, encounter_id)
    if not encounter:
        raise ValueError("就诊记录不存在")
    if encounter.status == "closed":
        raise ValueError("就诊已关闭，不能开检验申请")

    if not get_item(db, data.item_id):
        raise ValueError("检验项目不存在")

    request = LabRequest(
        encounter_id=encounter_id,
        item_id=data.item_id,
        status="pending",
        requested_by=requested_by,
    )
    db.add(request)
    db.flush()

    # 计费：检验费（项目价格快照）
    if request.item.price > 0:
        add_charge(
            db,
            encounter_id=encounter_id,
            source_type="lab_request",
            source_id=request.id,
            charge_type="lab",
            item_name=f"检验：{request.item.name}",
            quantity=1,
            unit_price=request.item.price,
            insurance_ratio=0.7,
        )

    db.commit()
    db.refresh(request)
    return request


def get_request(db: Session, request_id: int) -> LabRequest | None:
    return db.get(LabRequest, request_id)


def list_requests(db: Session, encounter_id: int) -> list[LabRequest]:
    """就诊的全部检验申请（按申请顺序）。"""
    return (
        db.query(LabRequest)
        .filter(LabRequest.encounter_id == encounter_id)
        .order_by(LabRequest.id)
        .all()
    )


def report_request(db: Session, request_id: int, result: str) -> LabRequest:
    """检验科回传结果：仅 pending 可报告。"""
    request = get_request(db, request_id)
    if not request:
        raise ValueError("检验申请不存在")
    if request.status != "pending":
        raise ValueError("该检验申请已出结果")

    request.status = "reported"
    request.result = result
    request.reported_at = datetime.now()
    db.commit()
    db.refresh(request)

    _notify_result_ready(db, request.encounter_id, "检验")
    return request


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
