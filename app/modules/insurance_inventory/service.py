"""医保进销存：从库存流水生成明细并上传（Mock/真实接口）。"""
import json
from datetime import date, datetime, time as dt_time

from sqlalchemy.orm import Session

from app.modules.drug.models import Drug
from app.modules.stock_ledger.models import StockMovement

from .adapter import submit_inventory
from .models import InsuranceInventoryUpload

# 流水单据类型 → 医保进销存业务类型
_BUSINESS_TYPE = {
    "purchase": "采购入库",
    "inbound": "入库",
    "stock_in": "入库",
    "outbound": "出库",
    "dispense": "发药销售",
    "dispense_return": "退药",
    "return": "退库",
    "scrap": "报损",
    "adjust": "盘点调整",
    "usage": "使用",
}


def _business_type(ref_type: str, direction: str) -> str:
    if ref_type in _BUSINESS_TYPE:
        return _BUSINESS_TYPE[ref_type]
    return "入库" if direction == "in" else "出库"


def build_records(db: Session, start_date: date, end_date: date) -> list[dict]:
    """按期间生成医保进销存明细（仅药品）。"""
    if start_date > end_date:
        raise ValueError("开始日期不能晚于结束日期")
    rows = (
        db.query(StockMovement)
        .filter(
            StockMovement.kind == "drug",
            StockMovement.created_at >= datetime.combine(start_date, dt_time.min),
            StockMovement.created_at <= datetime.combine(end_date, dt_time.max),
        )
        .order_by(StockMovement.id)
        .all()
    )
    drug_ids = {row.drug_id for row in rows if row.drug_id}
    drugs = {
        drug.id: drug
        for drug in db.query(Drug).filter(Drug.id.in_(drug_ids)).all()
    } if drug_ids else {}

    records = []
    for row in rows:
        drug = drugs.get(row.drug_id)
        records.append(
            {
                "insurance_code": (drug.insurance_code if drug else "") or "",
                "drug_name": row.name,
                "spec": row.spec or "",
                "dosage_form": (drug.dosage_form if drug else "") or "",
                "unit": row.unit or "",
                "batch_no": row.batch_no or "",
                "expiry": row.expiry.isoformat() if row.expiry else "",
                "warehouse": row.warehouse,
                "direction": row.direction,
                "business_type": _business_type(row.ref_type, row.direction),
                "quantity": row.quantity,
                "unit_price": row.unit_price,
                "amount": row.amount,
                "occurred_at": row.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                "ref_type": row.ref_type,
                "ref_id": row.ref_id,
                "balance_after": row.balance_after,
            }
        )
    return records


def preview(db: Session, start_date: date, end_date: date) -> dict:
    records = build_records(db, start_date, end_date)
    return {
        "start_date": start_date,
        "end_date": end_date,
        "record_count": len(records),
        "total_amount": round(sum(row["amount"] for row in records), 2),
        "unmatched_count": sum(1 for row in records if not row["insurance_code"]),
        "records": records[:50],
    }


def _submit_mock(payload: dict) -> dict:
    """兼容旧调用：Mock 接收（实际由 adapter 根据配置决定 Mock/HTTP）。"""
    if not payload.get("records"):
        return {"code": "1", "message": "无进销存明细", "receipt_no": ""}
    return {
        "code": "0",
        "message": "医保进销存接收成功（Mock）",
        "receipt_no": "MOCK-LOCAL",
        "received_count": len(payload["records"]),
    }


def create_upload(
    db: Session, start_date: date, end_date: date, created_by: str = ""
) -> InsuranceInventoryUpload:
    records = build_records(db, start_date, end_date)
    if not records:
        raise ValueError("该期间没有药品进销存记录")

    last = db.query(InsuranceInventoryUpload.id).order_by(
        InsuranceInventoryUpload.id.desc()
    ).first()
    next_id = (last[0] if last else 0) + 1
    upload_no = f"INV{datetime.now():%Y%m%d}{next_id:04d}"
    payload = {
        "upload_no": upload_no,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "records": records,
    }
    upload = InsuranceInventoryUpload(
        upload_no=upload_no,
        start_date=start_date,
        end_date=end_date,
        record_count=len(records),
        total_amount=round(sum(row["amount"] for row in records), 2),
        status="submitted",
        payload=json.dumps(payload, ensure_ascii=False),
        created_by=created_by,
        submitted_at=datetime.now(),
    )
    db.add(upload)
    db.flush()

    response = submit_inventory(db, payload)
    upload.response = json.dumps(response, ensure_ascii=False)
    upload.channel = response.get("channel", "mock")
    upload.status = "success" if response.get("code") == "0" else "failed"
    db.commit()
    db.refresh(upload)
    return upload


def list_uploads(db: Session, limit: int = 50) -> list[InsuranceInventoryUpload]:
    return (
        db.query(InsuranceInventoryUpload)
        .order_by(InsuranceInventoryUpload.id.desc())
        .limit(min(max(limit, 1), 200))
        .all()
    )


def get_upload(db: Session, upload_id: int) -> InsuranceInventoryUpload | None:
    return db.get(InsuranceInventoryUpload, upload_id)
