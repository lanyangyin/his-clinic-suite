"""药品追溯码：入库登记、出库移库、发药核销、退药回库。"""
from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.modules.drug.service import get_drug
from app.modules.encounter.models import Encounter
from app.modules.registration.models import Registration
from app.modules.warehouse.models import WarehouseStock

from .models import DrugTraceCode


def _clean_codes(codes: list[str]) -> list[str]:
    result = []
    for code in codes:
        text = (code or "").strip()
        if not text:
            continue
        if text in result:
            raise ValueError(f"追溯码重复：{text}")
        result.append(text)
    if not result:
        raise ValueError("请扫码或输入追溯码")
    return result


def _fetch(db: Session, codes: list[str]) -> list[DrugTraceCode]:
    rows = (
        db.query(DrugTraceCode)
        .filter(DrugTraceCode.trace_code.in_(codes))
        .all()
    )
    found = {row.trace_code for row in rows}
    missing = [code for code in codes if code not in found]
    if missing:
        raise ValueError(f"追溯码不存在：{', '.join(missing[:5])}")
    return rows


def scan_inbound(db: Session, data, operator: str = "") -> dict:
    """入库扫码：登记追溯码到总库（数量不能超过该批次总库库存）。"""
    if not data.drug_id:
        raise ValueError("入库扫码必须指定药品")
    if not data.batch_no:
        raise ValueError("入库扫码必须指定批号")
    drug = get_drug(db, data.drug_id)
    if not drug:
        raise ValueError("药品不存在")
    codes = _clean_codes(data.codes)

    stock = (
        db.query(WarehouseStock)
        .filter(
            WarehouseStock.drug_id == data.drug_id,
            WarehouseStock.batch_no == data.batch_no,
        )
        .first()
    )
    if not stock:
        raise ValueError("总库无该批次库存，请先完成入库")

    existing = (
        db.query(DrugTraceCode)
        .filter(DrugTraceCode.trace_code.in_(codes))
        .all()
    )
    if existing:
        raise ValueError(f"追溯码已存在：{existing[0].trace_code}")

    in_stock_count = (
        db.query(func.count(DrugTraceCode.id))
        .filter(
            DrugTraceCode.drug_id == data.drug_id,
            DrugTraceCode.batch_no == data.batch_no,
            DrugTraceCode.warehouse == "总库",
            DrugTraceCode.status == "in_stock",
        )
        .scalar()
        or 0
    )
    if in_stock_count + len(codes) > stock.quantity:
        raise ValueError(
            f"追溯码数量超过总库库存：现有 {in_stock_count} 码 / 库存 {stock.quantity}，本次 {len(codes)}"
        )

    for code in codes:
        db.add(
            DrugTraceCode(
                trace_code=code,
                drug_id=data.drug_id,
                batch_no=data.batch_no,
                warehouse="总库",
                status="in_stock",
                ref_type="inbound",
                ref_id=data.ref_id,
                scanned_by=operator,
            )
        )
    db.commit()
    return {
        "accepted": len(codes),
        "status": "in_stock",
        "message": f"入库扫码成功，{len(codes)} 个码登记到总库",
        "codes": codes,
    }


def scan_outbound(db: Session, data, operator: str = "") -> dict:
    """出库扫码：追溯码从总库移到药房（需先完成出库单）。"""
    codes = _clean_codes(data.codes)
    rows = _fetch(db, codes)
    target = data.target_warehouse or "药房"
    invalid = [
        row.trace_code
        for row in rows
        if row.status != "in_stock" or row.warehouse != "总库"
    ]
    if invalid:
        raise ValueError(f"以下追溯码不在总库在库状态：{', '.join(invalid[:5])}")
    for row in rows:
        row.warehouse = target
        row.ref_type = "outbound"
        row.ref_id = data.ref_id
        row.scanned_by = operator
        row.scanned_at = datetime.now()
    db.commit()
    return {
        "accepted": len(rows),
        "status": "in_stock",
        "message": f"出库扫码成功，{len(rows)} 个码移至{target}",
        "codes": codes,
    }


def scan_dispense(db: Session, data, operator: str = "") -> dict:
    """发药扫码：药房在库码核销为已使用，关联就诊/患者。"""
    codes = _clean_codes(data.codes)
    rows = _fetch(db, codes)
    invalid = [
        row.trace_code
        for row in rows
        if row.status != "in_stock" or row.warehouse != "药房"
    ]
    if invalid:
        raise ValueError(f"以下追溯码不在药房在库状态：{', '.join(invalid[:5])}")

    patient_id = None
    if data.encounter_id:
        encounter = db.get(Encounter, data.encounter_id)
        if not encounter:
            raise ValueError("就诊记录不存在")
        registration = db.get(Registration, encounter.registration_id)
        patient_id = registration.patient_id if registration else None

    for row in rows:
        row.status = "used"
        row.ref_type = "dispense"
        row.ref_id = data.ref_id or data.encounter_id
        row.encounter_id = data.encounter_id
        row.patient_id = patient_id
        row.scanned_by = operator
        row.scanned_at = datetime.now()
    db.commit()
    return {
        "accepted": len(rows),
        "status": "used",
        "message": f"发药扫码成功，{len(rows)} 个码已核销",
        "codes": codes,
    }


def scan_return(db: Session, data, operator: str = "") -> dict:
    """退药扫码：已使用追溯码退回药房在库（可再次发药）。"""
    codes = _clean_codes(data.codes)
    rows = _fetch(db, codes)
    invalid = [row.trace_code for row in rows if row.status != "used"]
    if invalid:
        raise ValueError(f"以下追溯码不是已使用状态：{', '.join(invalid[:5])}")
    for row in rows:
        row.status = "in_stock"
        row.warehouse = "药房"
        row.ref_type = "return"
        row.ref_id = data.ref_id
        row.encounter_id = None
        row.patient_id = None
        row.scanned_by = operator
        row.scanned_at = datetime.now()
        row.note = "退药回库"
    db.commit()
    return {
        "accepted": len(rows),
        "status": "in_stock",
        "message": f"退药扫码成功，{len(rows)} 个码回到药房",
        "codes": codes,
    }


def get_code(db: Session, trace_code: str) -> DrugTraceCode | None:
    return (
        db.query(DrugTraceCode)
        .filter(DrugTraceCode.trace_code == trace_code.strip())
        .first()
    )


def list_codes(
    db: Session,
    trace_code: str | None = None,
    drug_id: int | None = None,
    batch_no: str | None = None,
    status: str | None = None,
    warehouse: str | None = None,
    limit: int = 200,
    offset: int = 0,
) -> list[DrugTraceCode]:
    query = db.query(DrugTraceCode)
    if trace_code:
        query = query.filter(DrugTraceCode.trace_code == trace_code.strip())
    if drug_id is not None:
        query = query.filter(DrugTraceCode.drug_id == drug_id)
    if batch_no:
        query = query.filter(DrugTraceCode.batch_no == batch_no)
    if status:
        query = query.filter(DrugTraceCode.status == status)
    if warehouse:
        query = query.filter(DrugTraceCode.warehouse == warehouse)
    return (
        query.order_by(DrugTraceCode.id.desc())
        .offset(max(offset, 0))
        .limit(min(max(limit, 1), 500))
        .all()
    )


def summary(db: Session, drug_id: int | None = None, batch_no: str | None = None) -> dict:
    query = db.query(
        DrugTraceCode.status,
        DrugTraceCode.warehouse,
        func.count(DrugTraceCode.id),
    )
    if drug_id is not None:
        query = query.filter(DrugTraceCode.drug_id == drug_id)
    if batch_no:
        query = query.filter(DrugTraceCode.batch_no == batch_no)
    rows = query.group_by(DrugTraceCode.status, DrugTraceCode.warehouse).all()
    data = [{"status": status, "warehouse": warehouse, "count": count} for status, warehouse, count in rows]
    return {"items": data, "total": sum(item["count"] for item in data)}
