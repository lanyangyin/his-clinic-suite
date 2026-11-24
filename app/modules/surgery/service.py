"""手术室：排班、安全核查、术中记录、器械清点、复苏、CSSD 包关联。"""
import hashlib
from datetime import datetime

from sqlalchemy.orm import Session

from app import settings
from app.modules.encounter.service import get_encounter
from app.modules.charges.models import ChargeItem, EncounterCharge
from app.modules.charges.service import add_charge
from app.modules.patient.models import Patient
from app.modules.patient.service import get_patient

from .models import (
    OperatingRoom,
    SurgeryCase,
    SurgeryInstrumentCount,
    SurgeryPreopAssessment,
    AnesthesiaRecord,
    SurgeryRecord,
    SurgeryRecovery,
    SurgerySafetyCheck,
    SurgerySignature,
)
from .schemas import (
    AnesthesiaCreate,
    CaseCreate,
    CountCreate,
    PreopCreate,
    RecordCreate,
    RecoveryCreate,
    RoomCreate,
    SafetyCreate,
)


def create_room(db: Session, data: RoomCreate) -> OperatingRoom:
    if db.query(OperatingRoom).filter(OperatingRoom.code == data.code).first():
        raise ValueError("手术间编码已存在")
    row = OperatingRoom(**data.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def list_rooms(db: Session) -> list[OperatingRoom]:
    return db.query(OperatingRoom).order_by(OperatingRoom.code).all()


def _next_no(db: Session) -> str:
    last = db.query(SurgeryCase.id).order_by(SurgeryCase.id.desc()).first()
    return f"SR{datetime.now():%Y%m%d}{(last[0] if last else 0) + 1:04d}"


def _check_room_conflict(
    db: Session, room_id: int | None, scheduled_at: datetime, exclude_id: int | None = None
) -> None:
    if room_id is None:
        return
    query = db.query(SurgeryCase).filter(
        SurgeryCase.room_id == room_id,
        SurgeryCase.scheduled_at == scheduled_at,
        SurgeryCase.status.in_(("scheduled", "in_progress")),
    )
    if exclude_id is not None:
        query = query.filter(SurgeryCase.id != exclude_id)
    if query.first():
        raise ValueError("该手术间该时段已有手术")


def create_case(db: Session, data: CaseCreate, created_by: str = "") -> SurgeryCase:
    if not get_patient(db, data.patient_id):
        raise ValueError("患者不存在")
    if data.encounter_id is not None and not get_encounter(db, data.encounter_id):
        raise ValueError("就诊记录不存在")
    if data.room_id is not None and not db.get(OperatingRoom, data.room_id):
        raise ValueError("手术间不存在")
    _check_room_conflict(db, data.room_id, data.scheduled_at or datetime.now())
    price = data.price
    insurance_ratio = 0.0
    if data.charge_item_id is not None:
        item = db.get(ChargeItem, data.charge_item_id)
        if not item:
            raise ValueError("收费项目不存在")
        price = price or item.price
        insurance_ratio = item.insurance_ratio
    row = SurgeryCase(
        signatures_required=settings.SURGERY_REQUIRE_SIGNATURES,
        surgery_no=_next_no(db),
        patient_id=data.patient_id,
        encounter_id=data.encounter_id,
        room_id=data.room_id,
        procedure_name=data.procedure_name,
        diagnosis=data.diagnosis,
        surgeon=data.surgeon,
        anesthesia_type=data.anesthesia_type,
        scheduled_at=data.scheduled_at or datetime.now(),
        charge_item_id=data.charge_item_id,
        price=price,
        notes=data.notes,
        created_by=created_by,
    )
    db.add(row)
    db.flush()
    if data.encounter_id is not None and price > 0:
        add_charge(
            db,
            encounter_id=data.encounter_id,
            source_type="surgery_case",
            source_id=row.id,
            charge_type="treatment",
            charge_item_id=data.charge_item_id,
            item_name=f"手术：{data.procedure_name}",
            quantity=1,
            unit_price=price,
            insurance_ratio=insurance_ratio,
        )
    db.commit()
    db.refresh(row)
    return row


def reschedule_case(
    db: Session, case_id: int, data, operator: str = ""
) -> SurgeryCase:
    case = get_case(db, case_id)
    if not case:
        raise ValueError("手术不存在")
    if case.status != "scheduled":
        raise ValueError("仅未开始的已排班手术可以改期")
    room_id = case.room_id if data.room_id is None else data.room_id
    if room_id is not None and not db.get(OperatingRoom, room_id):
        raise ValueError("手术间不存在")
    _check_room_conflict(db, room_id, data.scheduled_at, exclude_id=case.id)
    case.room_id = room_id
    case.scheduled_at = data.scheduled_at
    case.rescheduled_at = datetime.now()
    case.rescheduled_by = operator
    case.reschedule_reason = data.reason.strip()
    db.commit()
    db.refresh(case)
    return case


def cancel_case(db: Session, case_id: int, reason: str, operator: str = "") -> SurgeryCase:
    """取消未开始手术：释放排班，未收费则撤销待收手术费；已收费必须先退费。"""
    case = get_case(db, case_id)
    if not case:
        raise ValueError("手术不存在")
    if case.status != "scheduled":
        raise ValueError("仅已排班且未开始的手术可以取消")
    if not reason.strip():
        raise ValueError("请填写取消原因")
    charge = (
        db.query(EncounterCharge)
        .filter(
            EncounterCharge.source_type == "surgery_case",
            EncounterCharge.source_id == case.id,
        )
        .first()
    )
    if charge:
        if charge.status != "pending":
            raise ValueError("该手术费用已收费，请先退费后再取消")
        db.delete(charge)
    case.status = "cancelled"
    case.cancelled_at = datetime.now()
    case.cancelled_by = operator
    case.cancel_reason = reason.strip()
    db.commit()
    db.refresh(case)
    return case


def list_cases(db: Session, status: str | None = None) -> list[dict]:
    query = db.query(SurgeryCase, Patient).join(Patient, SurgeryCase.patient_id == Patient.id)
    if status:
        query = query.filter(SurgeryCase.status == status)
    rows = query.order_by(SurgeryCase.scheduled_at.desc()).all()
    return [
        {
            "id": case.id,
            "surgery_no": case.surgery_no,
            "patient_id": case.patient_id,
            "patient_name": patient.name,
            "encounter_id": case.encounter_id,
            "room_id": case.room_id,
            "room_name": case.room_name,
            "procedure_name": case.procedure_name,
            "diagnosis": case.diagnosis,
            "surgeon": case.surgeon,
            "anesthesia_type": case.anesthesia_type,
            "scheduled_at": case.scheduled_at,
            "status": case.status,
            "started_at": case.started_at,
            "completed_at": case.completed_at,
        }
        for case, patient in rows
    ]


def get_case(db: Session, case_id: int) -> SurgeryCase | None:
    return db.get(SurgeryCase, case_id)


def detail(db: Session, case_id: int) -> dict | None:
    case = get_case(db, case_id)
    if not case:
        return None
    return {
        "case": case,
        "checks": case.checks,
        "records": case.records,
        "counts": case.counts,
        "recovery": case.recovery,
        "preop": case.preop,
        "anesthesia": case.anesthesia,
    }


def add_safety(db: Session, case_id: int, data: SafetyCreate, operator: str = "") -> SurgerySafetyCheck:
    case = get_case(db, case_id)
    if not case:
        raise ValueError("手术不存在")
    if case.status == "completed":
        raise ValueError("手术已完成，不能修改安全核查")
    exists = (
        db.query(SurgerySafetyCheck)
        .filter(SurgerySafetyCheck.case_id == case_id, SurgerySafetyCheck.phase == data.phase)
        .first()
    )
    if exists:
        raise ValueError("该阶段安全核查已完成")
    row = SurgerySafetyCheck(
        case_id=case_id,
        phase=data.phase,
        checklist=data.checklist,
        completed_by=operator,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def start_case(db: Session, case_id: int, operator: str = "") -> SurgeryCase:
    case = get_case(db, case_id)
    if not case:
        raise ValueError("手术不存在")
    if case.status != "scheduled":
        raise ValueError("该手术当前状态不可开始")
    if not case.preop:
        raise ValueError("请先完成术前访视/麻醉评估")
    if not case.preop.consent:
        raise ValueError("术前访视尚未完成知情同意")
    sign_in = (
        db.query(SurgerySafetyCheck)
        .filter(SurgerySafetyCheck.case_id == case_id, SurgerySafetyCheck.phase == "sign_in")
        .first()
    )
    if not sign_in:
        raise ValueError("请先完成术前安全核查（sign_in）")
    if case.signatures_required:
        roles = {
            row.role
            for row in db.query(SurgerySignature).filter(SurgerySignature.case_id == case_id).all()
        }
        missing = {"surgeon", "anesthesia", "nurse"} - roles
        if missing:
            raise ValueError("缺少手术三方电子签名：" + "、".join(sorted(missing)))
    team = {
        (case.surgeon or "").strip(),
        (case.preop.anesthesiologist or "").strip(),
        (sign_in.completed_by or "").strip(),
    }
    if all(team) and len(team) < 3:
        raise ValueError("手术医生、麻醉医生、安全核查护士不能为同一人")
    case.status = "in_progress"
    case.started_at = datetime.now()
    db.commit()
    db.refresh(case)
    return case


def add_record(db: Session, case_id: int, data: RecordCreate, operator: str = "") -> SurgeryRecord:
    case = get_case(db, case_id)
    if not case:
        raise ValueError("手术不存在")
    if case.status != "in_progress":
        raise ValueError("只有手术中的病例可以写术中记录")
    row = SurgeryRecord(case_id=case_id, **data.model_dump(), recorded_by=operator)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def add_count(db: Session, case_id: int, data: CountCreate, operator: str = "") -> SurgeryInstrumentCount:
    case = get_case(db, case_id)
    if not case:
        raise ValueError("手术不存在")
    if case.status != "in_progress":
        raise ValueError("只有手术中的病例可以清点器械")
    row = SurgeryInstrumentCount(
        case_id=case_id,
        phase=data.phase,
        item_name=data.item_name,
        expected=data.expected,
        actual=data.actual,
        matched=data.expected == data.actual,
        counted_by=operator,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def complete_case(db: Session, case_id: int, operator: str = "") -> SurgeryCase:
    case = get_case(db, case_id)
    if not case:
        raise ValueError("手术不存在")
    if case.status != "in_progress":
        raise ValueError("只有手术中的病例可以结束")
    sign_out = (
        db.query(SurgerySafetyCheck)
        .filter(SurgerySafetyCheck.case_id == case_id, SurgerySafetyCheck.phase == "sign_out")
        .first()
    )
    if not sign_out:
        raise ValueError("请先完成离室安全核查（sign_out）")
    after = (
        db.query(SurgeryInstrumentCount)
        .filter(SurgeryInstrumentCount.case_id == case_id, SurgeryInstrumentCount.phase == "after")
        .all()
    )
    if not after:
        raise ValueError("请先完成术后器械清点")
    if any(not row.matched for row in after):
        raise ValueError("术后器械清点不符，不能结束手术")
    case.status = "completed"
    case.completed_at = datetime.now()
    if case.anesthesia:
        case.anesthesia.ended_at = datetime.now()
    db.commit()
    db.refresh(case)
    return case


def add_recovery(db: Session, case_id: int, data: RecoveryCreate, operator: str = "") -> SurgeryRecovery:
    case = get_case(db, case_id)
    if not case:
        raise ValueError("手术不存在")
    if case.status != "completed":
        raise ValueError("手术未完成，不能登记复苏")
    row = SurgeryRecovery(
        case_id=case_id,
        pacu_in=datetime.now(),
        vitals=data.vitals,
        score=data.score,
        nurse=operator,
        note=data.note,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def attach_package(db: Session, case_id: int, package_id: int, operator: str = "") -> dict:
    from app.modules.cssd.models import InstrumentPackage

    case = get_case(db, case_id)
    if not case:
        raise ValueError("手术不存在")
    package = db.get(InstrumentPackage, package_id)
    if not package:
        raise ValueError("器械包不存在")
    if package.status not in ("sterilized", "issued"):
        raise ValueError("该器械包当前不可使用")
    package.surgery_case_id = case.id
    package.status = "used"
    db.commit()
    return {"case_id": case.id, "package_id": package.id, "package_code": package.package_code}


def add_material(db: Session, case_id: int, data, operator: str = ""):
    from app.modules.procedure_materials.service import consume_material

    case = get_case(db, case_id)
    if not case:
        raise ValueError("手术不存在")
    if case.status not in ("in_progress", "completed"):
        raise ValueError("只有手术中/已完成的手术可以登记耗材")
    return consume_material(
        db,
        source_type="surgery",
        source_id=case.id,
        encounter_id=case.encounter_id,
        material_id=data.material_id,
        quantity=data.quantity,
        warehouse=data.warehouse,
        operator=operator,
    )

def save_preop(db: Session, case_id: int, data: PreopCreate, operator: str = "") -> SurgeryPreopAssessment:
    case = get_case(db, case_id)
    if not case:
        raise ValueError("手术不存在")
    if case.status != "scheduled":
        raise ValueError("只有已排班手术可以填写术前访视")
    row = case.preop
    if row:
        for key, value in data.model_dump().items():
            setattr(row, key, value)
        row.assessed_by = operator
        row.assessed_at = datetime.now()
    else:
        row = SurgeryPreopAssessment(
            case_id=case.id, **data.model_dump(), assessed_by=operator
        )
        db.add(row)
    db.commit()
    db.refresh(row)
    return row


def save_anesthesia(db: Session, case_id: int, data: AnesthesiaCreate, operator: str = "") -> AnesthesiaRecord:
    case = get_case(db, case_id)
    if not case:
        raise ValueError("手术不存在")
    if case.status not in ("in_progress", "completed"):
        raise ValueError("手术未开始，不能写麻醉记录")
    row = case.anesthesia
    if row:
        for key, value in data.model_dump().items():
            setattr(row, key, value)
        row.recorded_by = operator
        row.recorded_at = datetime.now()
    else:
        row = AnesthesiaRecord(
            case_id=case.id,
            started_at=case.started_at or datetime.now(),
            **data.model_dump(),
            recorded_by=operator,
        )
        db.add(row)
    db.commit()
    db.refresh(row)
    return row


def require_signatures(db: Session, case_id: int) -> SurgeryCase:
    case = get_case(db, case_id)
    if not case:
        raise ValueError("手术不存在")
    case.signatures_required = True
    db.commit()
    db.refresh(case)
    return case


def sign_case(
    db: Session, case_id: int, role: str, password: str, user
) -> SurgerySignature:
    from app.modules.auth.service import verify_password

    case = get_case(db, case_id)
    if not case:
        raise ValueError("手术不存在")
    allowed = {
        "surgeon": {"surgery"},
        "anesthesia": {"anesthesia"},
        "nurse": {"surgery_nurse"},
    }
    if role not in allowed:
        raise ValueError("签名角色无效")
    user_role = getattr(user, "role", "")
    if user_role not in allowed[role] and user_role != "admin":
        raise ValueError("当前账号角色不能签署该角色")
    if not verify_password(user, password):
        raise ValueError("签名口令错误")
    content = f"{case.id}|{role}|{user.username}|{datetime.now().isoformat()}"
    row = (
        db.query(SurgerySignature)
        .filter(SurgerySignature.case_id == case_id, SurgerySignature.role == role)
        .first()
    )
    if row is None:
        row = SurgerySignature(case_id=case_id, role=role)
        db.add(row)
    row.username = user.username
    row.content_hash = hashlib.sha256(content.encode()).hexdigest()
    row.signed_at = datetime.now()
    db.commit()
    db.refresh(row)
    return row


def list_signatures(db: Session, case_id: int) -> list[SurgerySignature]:
    return (
        db.query(SurgerySignature)
        .filter(SurgerySignature.case_id == case_id)
        .order_by(SurgerySignature.id)
        .all()
    )
