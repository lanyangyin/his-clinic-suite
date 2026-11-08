from sqlalchemy import func
from sqlalchemy.orm import Session

from .models import DictEntry
from .schemas import DictEntryCreate, DictEntryUpdate


def create_entry(db: Session, dict_type: str, data: DictEntryCreate) -> DictEntry:
    """新增字典条目：类型内编码唯一。"""
    existing = (
        db.query(DictEntry)
        .filter(DictEntry.dict_type == dict_type, DictEntry.code == data.code)
        .first()
    )
    if existing:
        raise ValueError("该字典类型下编码已存在")

    entry = DictEntry(
        dict_type=dict_type,
        code=data.code,
        name=data.name,
        sort_order=data.sort_order,
        active=True,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def get_entry(db: Session, dict_type: str, code: str) -> DictEntry | None:
    return (
        db.query(DictEntry)
        .filter(DictEntry.dict_type == dict_type, DictEntry.code == code)
        .first()
    )


def list_entries(
    db: Session, dict_type: str, active_only: bool = False
) -> list[DictEntry]:
    query = db.query(DictEntry).filter(DictEntry.dict_type == dict_type)
    if active_only:
        query = query.filter(DictEntry.active.is_(True))
    return query.order_by(DictEntry.sort_order, DictEntry.id).all()


def list_types(db: Session) -> list[dict]:
    rows = (
        db.query(
            DictEntry.dict_type,
            func.count(DictEntry.id).label("cnt"),
        )
        .group_by(DictEntry.dict_type)
        .order_by(DictEntry.dict_type)
        .all()
    )
    return [{"dict_type": row.dict_type, "entry_count": row.cnt} for row in rows]


def update_entry(
    db: Session, dict_type: str, code: str, data: DictEntryUpdate
) -> DictEntry:
    """更新条目（名称/排序/启用状态）。"""
    entry = get_entry(db, dict_type, code)
    if not entry:
        raise ValueError("字典条目不存在")

    for field, value in data.model_dump(exclude_none=True).items():
        setattr(entry, field, value)
    db.commit()
    db.refresh(entry)
    return entry
