from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.modules.auth.security import require_role

from .schemas import DictEntryCreate, DictEntryResponse, DictEntryUpdate, DictTypeItem
from .service import (
    create_entry,
    get_entry,
    list_entries,
    list_types,
    update_entry,
)

router = APIRouter(prefix="/dict", tags=["dict"])


@router.post("/{dict_type}/entries", response_model=DictEntryResponse, status_code=201)
def new_entry(
    dict_type: str,
    data: DictEntryCreate,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("admin")),
):
    try:
        return create_entry(db, dict_type, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{dict_type}/entries", response_model=list[DictEntryResponse])
def get_entries(
    dict_type: str, active_only: bool = False, db: Session = Depends(get_db)
):
    return list_entries(db, dict_type, active_only)


@router.get("/{dict_type}/entries/{code}", response_model=DictEntryResponse)
def get_entry_one(dict_type: str, code: str, db: Session = Depends(get_db)):
    entry = get_entry(db, dict_type, code)
    if not entry:
        raise HTTPException(status_code=404, detail="字典条目不存在")
    return entry


@router.put("/{dict_type}/entries/{code}", response_model=DictEntryResponse)
def update_entry_one(
    dict_type: str,
    code: str,
    data: DictEntryUpdate,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("admin")),
):
    try:
        return update_entry(db, dict_type, code, data)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/types", response_model=list[DictTypeItem])
def get_types(db: Session = Depends(get_db)):
    return list_types(db)
