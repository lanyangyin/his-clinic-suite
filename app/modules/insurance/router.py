from datetime import date

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.modules.auth.security import require_read_login, require_role

from . import national
from .models import InsuranceTransaction
from .workbench import encounter_risks, workbench

router = APIRouter(prefix="/insurance", tags=["insurance"], dependencies=[Depends(require_read_login)])


@router.get("/national/status")
def national_status(
    db: Session = Depends(get_db),
    _: None = Depends(require_role("admin", "cashier")),
):
    cfg = national.config(db)
    return {
        "configured": cfg.configured,
        "enabled": cfg.enabled,
        "mock": cfg.mock,
        "missing": cfg.missing(),
        "supported": sorted(national.SUPPORTED),
        "security_mode": cfg.security_mode,
        "infver": cfg.infver,
        "recer_sys_code": cfg.recer_sys_code,
        "fixmedins_code": cfg.org_code,
        "mdtrtarea_admvs": cfg.effective_mdtrtarea,
        "insuplc_admdvs": cfg.effective_insuplc,
        "timeout": cfg.timeout,
        "retry": cfg.retry,
        "note": (
            "plain 模式可直接对接允许明文 input 的第三方模拟器；"
            "sm2_sm4 模式参数已预留，但本版本尚未实现 SM2/SM4 封装，不会伪造成功"
        ),
    }


@router.post("/national/pre-settle/{encounter_id}")
def national_pre_settle(
    encounter_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_role("cashier", "admin")),
):
    try:
        return national.pre_settle(db, encounter_id, user.username)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except national.NationalInsuranceNotConfigured as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.post("/national/settle/{encounter_id}")
def national_settle(
    encounter_id: int,
    setl_id: str = Body(default="", embed=True),
    db: Session = Depends(get_db),
    user=Depends(require_role("cashier", "admin")),
):
    try:
        return national.settle(db, encounter_id, user.username, setl_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except national.NationalInsuranceNotConfigured as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.post("/national/cancel-settle/{encounter_id}")
def national_cancel_settle(
    encounter_id: int,
    setl_id: str = Body(..., embed=True),
    db: Session = Depends(get_db),
    user=Depends(require_role("cashier", "admin")),
):
    try:
        return national.cancel_settle(db, encounter_id, setl_id, user.username)
    except national.NationalInsuranceNotConfigured as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/national/transactions")
def national_transactions(
    encounter_id: int | None = None,
    limit: int = 100,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("admin", "cashier")),
):
    query = db.query(InsuranceTransaction).filter(InsuranceTransaction.infno != "")
    if encounter_id is not None:
        query = query.filter(InsuranceTransaction.encounter_id == encounter_id)
    rows = query.order_by(InsuranceTransaction.id.desc()).limit(min(max(limit, 1), 500)).all()
    return [
        {
            "id": row.id,
            "encounter_id": row.encounter_id,
            "infno": row.infno,
            "kind": row.kind,
            "status": row.status,
            "mode": row.mode,
            "settlement_no": row.settlement_no,
            "operator": row.operator,
            "message": row.message,
            "created_at": row.created_at,
        }
        for row in rows
    ]


@router.get("/workbench")
def get_workbench(
    start_date: date | None = None,
    end_date: date | None = None,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("admin")),
):
    return workbench(db, start_date, end_date)


@router.get("/transactions")
def get_transactions(
    encounter_id: int | None = None,
    limit: int = 100,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("doctor", "admin")),
):
    query = db.query(InsuranceTransaction)
    if encounter_id is not None:
        query = query.filter(InsuranceTransaction.encounter_id == encounter_id)
    rows = query.order_by(InsuranceTransaction.id.desc()).limit(min(max(limit, 1), 500)).all()
    return [
        {
            "id": row.id,
            "encounter_id": row.encounter_id,
            "kind": row.kind,
            "drug_name": row.drug_name,
            "quantity": row.quantity,
            "ratio": row.ratio,
            "result": row.result,
            "message": row.message,
            "settlement_no": row.settlement_no,
            "operator": row.operator,
            "created_at": row.created_at,
        }
        for row in rows
    ]


@router.get("/risks/encounter/{encounter_id}")
def get_encounter_risks(
    encounter_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("doctor", "admin")),
):
    data = encounter_risks(db, encounter_id)
    if not data:
        raise HTTPException(status_code=404, detail="就诊记录不存在")
    return data
