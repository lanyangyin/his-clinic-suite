from datetime import datetime

from sqlalchemy.orm import Session

from app.modules.drug.service import get_drug
from app.modules.patient.service import get_patient
from app.modules.staff.service import get_doctor

from .models import (
    Admission,
    Bed,
    InpatientCharge,
    InpatientDispenseRequest,
    InpatientOrder,
    NursingNote,
    OrderExecution,
    VitalSign,
    Ward,
)
from .schemas import (
    AdmissionCreate,
    BedCreate,
    NursingNoteCreate,
    OrderCreate,
    VitalSignCreate,
    WardCreate,
)


def create_ward(db: Session, data: WardCreate) -> Ward:
    """创建病区：同名病区返回已有记录。"""
    existing = db.query(Ward).filter(Ward.name == data.name).first()
    if existing:
        return existing
    ward = Ward(name=data.name)
    db.add(ward)
    db.commit()
    db.refresh(ward)
    return ward


def get_ward(db: Session, ward_id: int) -> Ward | None:
    return db.get(Ward, ward_id)


def create_bed(db: Session, data: BedCreate) -> Bed:
    """创建床位：病区必须存在，床号病区内唯一。"""
    if not get_ward(db, data.ward_id):
        raise ValueError("病区不存在")
    existing = (
        db.query(Bed)
        .filter(Bed.ward_id == data.ward_id, Bed.code == data.code)
        .first()
    )
    if existing:
        raise ValueError("该病区床位号已存在")

    bed = Bed(ward_id=data.ward_id, code=data.code, status="empty")
    db.add(bed)
    db.commit()
    db.refresh(bed)
    return bed


def get_bed(db: Session, bed_id: int) -> Bed | None:
    return db.get(Bed, bed_id)


def list_beds(db: Session, ward_id: int) -> list[Bed]:
    """病区的全部床位（按床号）。"""
    return (
        db.query(Bed)
        .filter(Bed.ward_id == ward_id)
        .order_by(Bed.code)
        .all()
    )


def create_admission(db: Session, data: AdmissionCreate) -> Admission:
    """入院登记：患者/医生/床位校验，床位空闲则占用。"""
    if not get_patient(db, data.patient_id):
        raise ValueError("患者不存在")
    if not get_doctor(db, data.doctor_id):
        raise ValueError("医生不存在")

    bed = get_bed(db, data.bed_id)
    if not bed:
        raise ValueError("床位不存在")
    if bed.status != "empty":
        raise ValueError("床位已被占用")

    admission = Admission(
        patient_id=data.patient_id,
        doctor_id=data.doctor_id,
        bed_id=bed.id,
        status="in",
    )
    db.add(admission)
    bed.status = "occupied"
    db.commit()
    db.refresh(admission)
    return admission


def get_admission(db: Session, admission_id: int) -> Admission | None:
    return db.get(Admission, admission_id)


def list_admissions(
    db: Session, status: str | None = None, doctor_id: int | None = None
) -> list[Admission]:
    """住院记录列表（可按状态/医生过滤，最新在前）。"""
    query = db.query(Admission)
    if status is not None:
        query = query.filter(Admission.status == status)
    if doctor_id is not None:
        query = query.filter(Admission.doctor_id == doctor_id)
    return query.order_by(Admission.id.desc()).all()


def list_wards(db: Session) -> list[Ward]:
    return db.query(Ward).order_by(Ward.id).all()


def transfer_bed(db: Session, admission_id: int, new_bed_id: int) -> Admission:
    """转床：释放旧床、占用新床；仅限在院患者。"""
    admission = get_admission(db, admission_id)
    if not admission:
        raise ValueError("住院记录不存在")
    if admission.status != "in":
        raise ValueError("该患者已出院，不能转床")

    if new_bed_id == admission.bed_id:
        raise ValueError("目标床位与当前床位相同")

    new_bed = get_bed(db, new_bed_id)
    if not new_bed:
        raise ValueError("目标床位不存在")
    if new_bed.status != "empty":
        raise ValueError("目标床位已被占用")

    old_bed = get_bed(db, admission.bed_id)
    if old_bed:
        old_bed.status = "empty"
    new_bed.status = "occupied"
    admission.bed_id = new_bed.id
    db.commit()
    db.refresh(admission)
    return admission


def discharge(db: Session, admission_id: int) -> Admission:
    """出院：释放床位，记录出院时间。"""
    admission = get_admission(db, admission_id)
    if not admission:
        raise ValueError("住院记录不存在")
    if admission.status != "in":
        raise ValueError("该患者已出院")

    bed = get_bed(db, admission.bed_id)
    if bed:
        bed.status = "empty"
    admission.status = "discharged"
    admission.discharged_at = datetime.now()
    db.commit()
    db.refresh(admission)
    return admission


def create_order(db: Session, admission_id: int, data: OrderCreate) -> InpatientOrder:
    """开医嘱：仅限在院患者，校验医生与药品存在。"""
    admission = get_admission(db, admission_id)
    if not admission:
        raise ValueError("住院记录不存在")
    if admission.status != "in":
        raise ValueError("该患者已出院，不能开医嘱")
    if not get_doctor(db, data.doctor_id):
        raise ValueError("医生不存在")
    if not get_drug(db, data.drug_id):
        raise ValueError("药品不存在")

    order = InpatientOrder(
        admission_id=admission_id,
        doctor_id=data.doctor_id,
        drug_id=data.drug_id,
        order_type=data.order_type,
        quantity=data.quantity,
        status="open",
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return order


def get_order(db: Session, order_id: int) -> InpatientOrder | None:
    return db.get(InpatientOrder, order_id)


def list_orders(db: Session, admission_id: int) -> list[InpatientOrder]:
    """住院记录的全部医嘱（按开立顺序）。"""
    return (
        db.query(InpatientOrder)
        .filter(InpatientOrder.admission_id == admission_id)
        .order_by(InpatientOrder.id)
        .all()
    )


def stop_order(db: Session, order_id: int) -> InpatientOrder:
    """停止医嘱：仅 open 状态可停止。"""
    order = get_order(db, order_id)
    if not order:
        raise ValueError("医嘱不存在")
    if order.status != "open":
        raise ValueError("该医嘱已停止或已完成")

    order.status = "stopped"
    db.commit()
    db.refresh(order)
    return order


def execute_order(db: Session, order_id: int, note: str = "") -> OrderExecution:
    """护士执行医嘱：standing 可重复执行，stat 执行一次即完成；执行即计费。"""
    order = get_order(db, order_id)
    if not order:
        raise ValueError("医嘱不存在")
    if order.status != "open":
        raise ValueError("该医嘱已停止或已完成，不能执行")

    admission = get_admission(db, order.admission_id)
    if not admission or admission.status != "in":
        raise ValueError("该患者已出院，不能执行医嘱")

    execution = OrderExecution(order_id=order_id, note=note)
    db.add(execution)
    if order.order_type == "stat":
        # 原子状态机：并发执行同一 stat 医嘱只有一次生效
        affected = (
            db.query(InpatientOrder)
            .filter(
                InpatientOrder.id == order_id,
                InpatientOrder.status == "open",
            )
            .update(
                {InpatientOrder.status: "finished"},
                synchronize_session=False,
            )
        )
        if affected != 1:
            db.rollback()
            raise ValueError("该医嘱已停止或已完成，不能执行")
    db.flush()  # 先拿到 execution.id，再生成费用

    db.add(
        InpatientCharge(
            admission_id=order.admission_id,
            execution_id=execution.id,
            quantity=order.quantity,
            unit_price=order.drug.base_price,
            amount=round(order.quantity * order.drug.base_price, 2),
        )
    )
    db.commit()
    db.refresh(execution)
    return execution


def get_charges(db: Session, admission_id: int) -> list[InpatientCharge]:
    """住院费用明细（按产生顺序）。"""
    return (
        db.query(InpatientCharge)
        .filter(InpatientCharge.admission_id == admission_id)
        .order_by(InpatientCharge.id)
        .all()
    )


def get_bill(db: Session, admission_id: int) -> dict:
    """住院费用汇总（日清单总额）。"""
    charges = get_charges(db, admission_id)
    return {
        "admission_id": admission_id,
        "total_amount": round(sum(c.amount for c in charges), 2),
        "charge_count": len(charges),
    }


def create_dispense_request(db: Session, order_id: int) -> InpatientDispenseRequest:
    """护士发起摆药申请：仅限在院患者的执行中医嘱。"""
    order = get_order(db, order_id)
    if not order:
        raise ValueError("医嘱不存在")
    if order.status != "open":
        raise ValueError("该医嘱已停止或已完成，不能摆药")

    admission = get_admission(db, order.admission_id)
    if not admission or admission.status != "in":
        raise ValueError("该患者已出院，不能摆药")

    request = InpatientDispenseRequest(
        admission_id=order.admission_id,
        order_id=order.id,
        drug_id=order.drug_id,
        quantity=order.quantity,
        status="pending",
    )
    db.add(request)
    db.commit()
    db.refresh(request)
    return request


def get_dispense_request(db: Session, request_id: int) -> InpatientDispenseRequest | None:
    return db.get(InpatientDispenseRequest, request_id)


def list_dispense_requests(
    db: Session, admission_id: int
) -> list[InpatientDispenseRequest]:
    """住院记录的全部摆药单（按申请顺序）。"""
    return (
        db.query(InpatientDispenseRequest)
        .filter(InpatientDispenseRequest.admission_id == admission_id)
        .order_by(InpatientDispenseRequest.id)
        .all()
    )


def dispense_request(db: Session, request_id: int) -> InpatientDispenseRequest:
    """药房摆药：扣减库存（近效期先出），状态改为 dispensed。"""
    request = get_dispense_request(db, request_id)
    if not request:
        raise ValueError("摆药单不存在")
    if request.status != "pending":
        raise ValueError("该摆药单已处理")

    # 延迟导入避免循环依赖（pharmacy.service 依赖 encounter/billing）
    from app.modules.pharmacy.service import deduct_stock

    # 原子状态机：并发下发药请求时只有一个能成功
    affected = (
        db.query(InpatientDispenseRequest)
        .filter(
            InpatientDispenseRequest.id == request_id,
            InpatientDispenseRequest.status == "pending",
        )
        .update(
            {
                InpatientDispenseRequest.status: "dispensed",
                InpatientDispenseRequest.dispensed_at: datetime.now(),
            },
            synchronize_session=False,
        )
    )
    if affected != 1:
        raise ValueError("该摆药单已处理")

    deduct_stock(db, request.drug, request.quantity)

    db.commit()
    db.refresh(request)
    return request


def return_dispense(db: Session, request_id: int) -> InpatientDispenseRequest:
    """退药：已发药的摆药单退回，库存回补，状态改为 returned。"""
    request = get_dispense_request(db, request_id)
    if not request:
        raise ValueError("摆药单不存在")
    if request.status != "dispensed":
        raise ValueError("仅已发药的摆药单可以退药")

    from app.modules.pharmacy.service import restore_stock

    # 原子状态机：并发退药只有一次生效
    affected = (
        db.query(InpatientDispenseRequest)
        .filter(
            InpatientDispenseRequest.id == request_id,
            InpatientDispenseRequest.status == "dispensed",
        )
        .update(
            {
                InpatientDispenseRequest.status: "returned",
                InpatientDispenseRequest.returned_at: datetime.now(),
            },
            synchronize_session=False,
        )
    )
    if affected != 1:
        raise ValueError("仅已发药的摆药单可以退药")

    restore_stock(db, request.drug, request.quantity)

    db.commit()
    db.refresh(request)
    return request


def record_vital_signs(
    db: Session, admission_id: int, data: VitalSignCreate, recorded_by: str = ""
) -> VitalSign:
    """护士录入体征（体温单数据）。"""
    if not get_admission(db, admission_id):
        raise ValueError("住院记录不存在")

    vital = VitalSign(
        admission_id=admission_id,
        temperature=data.temperature,
        pulse=data.pulse,
        respiration=data.respiration,
        systolic=data.systolic,
        diastolic=data.diastolic,
        spo2=data.spo2,
        recorded_by=recorded_by,
    )
    db.add(vital)
    db.commit()
    db.refresh(vital)
    return vital


def list_vital_signs(db: Session, admission_id: int) -> list[VitalSign]:
    """住院记录的体征序列（体温单数据，按时间）。"""
    return (
        db.query(VitalSign)
        .filter(VitalSign.admission_id == admission_id)
        .order_by(VitalSign.id)
        .all()
    )


def create_nursing_note(
    db: Session, admission_id: int, data: NursingNoteCreate, recorded_by: str = ""
) -> NursingNote:
    """护士书写护理记录。"""
    if not get_admission(db, admission_id):
        raise ValueError("住院记录不存在")

    note = NursingNote(
        admission_id=admission_id,
        content=data.content,
        recorded_by=recorded_by,
    )
    db.add(note)
    db.commit()
    db.refresh(note)
    return note


def list_nursing_notes(db: Session, admission_id: int) -> list[NursingNote]:
    """住院记录的护理记录（按时间）。"""
    return (
        db.query(NursingNote)
        .filter(NursingNote.admission_id == admission_id)
        .order_by(NursingNote.id)
        .all()
    )
