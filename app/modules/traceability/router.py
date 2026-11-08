from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.modules.auth.security import require_role

from .schemas import TraceCodeResponse, TraceScanRequest, TraceScanResult
from .service import (
    get_code,
    list_codes,
    scan_dispense,
    scan_inbound,
    scan_outbound,
    scan_return,
    summary,
)

router = APIRouter(prefix="/trace", tags=["traceability"])


@router.post("/scan/inbound", response_model=TraceScanResult)
def trace_inbound(
    data: TraceScanRequest,
    db: Session = Depends(get_db),
    user=Depends(require_role("warehouse")),
):
    try:
        return scan_inbound(db, data, operator=user.username)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/scan/outbound", response_model=TraceScanResult)
def trace_outbound(
    data: TraceScanRequest,
    db: Session = Depends(get_db),
    user=Depends(require_role("warehouse")),
):
    try:
        return scan_outbound(db, data, operator=user.username)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/scan/dispense", response_model=TraceScanResult)
def trace_dispense(
    data: TraceScanRequest,
    db: Session = Depends(get_db),
    user=Depends(require_role("pharmacist")),
):
    try:
        return scan_dispense(db, data, operator=user.username)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/scan/return", response_model=TraceScanResult)
def trace_return(
    data: TraceScanRequest,
    db: Session = Depends(get_db),
    user=Depends(require_role("pharmacist")),
):
    try:
        return scan_return(db, data, operator=user.username)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/codes", response_model=list[TraceCodeResponse])
def get_codes(
    trace_code: str | None = None,
    drug_id: int | None = None,
    batch_no: str | None = None,
    status: str | None = None,
    warehouse: str | None = None,
    limit: int = 200,
    offset: int = 0,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("warehouse", "pharmacist")),
):
    return list_codes(db, trace_code, drug_id, batch_no, status, warehouse, limit, offset)


@router.get("/codes/summary")
def get_summary(
    drug_id: int | None = None,
    batch_no: str | None = None,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("warehouse", "pharmacist")),
):
    return summary(db, drug_id, batch_no)


@router.get("/codes/{trace_code}", response_model=TraceCodeResponse)
def get_one(
    trace_code: str,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("warehouse", "pharmacist")),
):
    row = get_code(db, trace_code)
    if not row:
        raise HTTPException(status_code=404, detail="追溯码不存在")
    return row
