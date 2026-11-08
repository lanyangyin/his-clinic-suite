from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.modules.auth.security import require_role
from app.modules.encounter.service import get_encounter

from .schemas import (
    ChargeItemCreate,
    ChargeItemResponse,
    ChargeSummary,
    EncounterChargeResponse,
)
from .service import (
    create_item,
    get_item,
    get_item_by_code,
    list_charges,
    list_items,
    summary,
)

router = APIRouter(prefix="/charges", tags=["charges"])


@router.post("/items/", response_model=ChargeItemResponse, status_code=201)
def new_item(
    data: ChargeItemCreate,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("admin")),
):
    try:
        return create_item(db, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/items/", response_model=list[ChargeItemResponse])
def get_items(category: str | None = None, db: Session = Depends(get_db)):
    return list_items(db, category)


@router.get("/items/by-code/{code}", response_model=ChargeItemResponse)
def get_one_by_code(code: str, db: Session = Depends(get_db)):
    item = get_item_by_code(db, code)
    if not item:
        raise HTTPException(status_code=404, detail="收费项目不存在")
    return item


@router.get("/items/{item_id}", response_model=ChargeItemResponse)
def get_one(item_id: int, db: Session = Depends(get_db)):
    item = get_item(db, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="收费项目不存在")
    return item


@router.get(
    "/encounters/{encounter_id}", response_model=list[EncounterChargeResponse]
)
def get_encounter_charges(encounter_id: int, db: Session = Depends(get_db)):
    if not get_encounter(db, encounter_id):
        raise HTTPException(status_code=404, detail="就诊记录不存在")
    return list_charges(db, encounter_id)


@router.get(
    "/encounters/{encounter_id}/summary", response_model=ChargeSummary
)
def get_encounter_charge_summary(encounter_id: int, db: Session = Depends(get_db)):
    if not get_encounter(db, encounter_id):
        raise HTTPException(status_code=404, detail="就诊记录不存在")
    return summary(db, encounter_id)
