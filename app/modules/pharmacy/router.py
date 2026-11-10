from datetime import datetime
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pathlib import Path
from sqlalchemy.orm import Session
import uuid

from app.database import get_db
from app.modules.auth.security import require_role

from .schemas import (
    DispenseRequest,
    DispenseResponse,
    PharmacyCallRequest,
    PharmacyCallResponse,
    PickupVerifyResponse,
    StockInRequest,
    StockInResponse,
    StockResponse,
)
from .service import (
    call_patient,
    dispense,
    get_dispense,
    get_stock,
    list_stocks,
    return_dispense,
    stock_in,
    verify_pickup,
    worklist,
)

router = APIRouter(prefix="/pharmacy", tags=["pharmacy"])


@router.post("/dispense", response_model=DispenseResponse, status_code=201)
def dispense_medicines(
    data: DispenseRequest,
    db: Session = Depends(get_db),
    user=Depends(require_role("pharmacist")),
):
    try:
        return dispense(db, data, operator=user.username)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/dispense/{dispense_id}/return", response_model=DispenseResponse)
def return_medicines(
    dispense_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_role("pharmacist")),
):
    """门诊退药：库存回补；退药后可继续退费。"""
    try:
        return return_dispense(db, dispense_id, operator=user.username)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/dispense/{dispense_id}", response_model=DispenseResponse)
def get_one(dispense_id: int, db: Session = Depends(get_db)):
    record = get_dispense(db, dispense_id)
    if not record:
        raise HTTPException(status_code=404, detail="发药记录不存在")
    return record


@router.post("/stock-in", response_model=StockInResponse, status_code=201)
def stock_in_medicines(
    data: StockInRequest,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("pharmacist")),
):
    try:
        return stock_in(db, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/stocks", response_model=list[StockResponse])
def get_stocks(drug_id: int | None = None, db: Session = Depends(get_db)):
    return list_stocks(db, drug_id)


@router.get("/stocks/{stock_id}", response_model=StockResponse)
def get_stock_one(stock_id: int, db: Session = Depends(get_db)):
    stock = get_stock(db, stock_id)
    if not stock:
        raise HTTPException(status_code=404, detail="库存记录不存在")
    return stock

@router.get("/worklist")
def pharmacy_worklist(
    db: Session = Depends(get_db),
    _: None = Depends(require_role("pharmacist")),
):
    return worklist(db)


@router.post("/calls/{encounter_id}", response_model=PharmacyCallResponse)
def call(
    encounter_id: int,
    data: PharmacyCallRequest,
    db: Session = Depends(get_db),
    user=Depends(require_role("pharmacist")),
):
    try:
        return call_patient(db, encounter_id, data.window_no, user.username, data.note)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/pickup-codes/{code}", response_model=PickupVerifyResponse)
def verify_code(
    code: str,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("pharmacist")),
):
    try:
        return verify_pickup(db, code)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


SIGNATURE_DIR = Path("data/pharmacy_signatures")


@router.post("/dispense/{dispense_id}/signature")
async def upload_signature(
    dispense_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: None = Depends(require_role("pharmacist")),
):
    record = get_dispense(db, dispense_id)
    if not record:
        raise HTTPException(status_code=404, detail="发药记录不存在")
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".jpg", ".jpeg", ".png"}:
        raise HTTPException(status_code=400, detail="仅支持 jpg/png 签名图片")
    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="签名图片不能超过 5MB")
    SIGNATURE_DIR.mkdir(parents=True, exist_ok=True)
    name = f"{dispense_id}_{uuid.uuid4().hex}{suffix}"
    path = SIGNATURE_DIR / name
    path.write_bytes(content)
    record.signature_path = str(path).replace("\\", "/")
    record.signed_at = record.signed_at or datetime.now()
    db.commit()
    return {"dispense_id": record.id, "signature_path": record.signature_path}
