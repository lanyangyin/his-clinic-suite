from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .models import Campus, Room
from .schemas import CampusCreate, RoomCreate


def create_campus(db: Session, data: CampusCreate) -> Campus:
    existing = db.query(Campus).filter(Campus.code == data.code).first()
    if existing:
        raise ValueError("院区编码已存在")
    campus = Campus(**data.model_dump())
    db.add(campus)
    db.commit()
    db.refresh(campus)
    return campus


def get_campus(db: Session, campus_id: int) -> Campus | None:
    return db.get(Campus, campus_id)


def list_campuses(db: Session) -> list[Campus]:
    return db.query(Campus).order_by(Campus.id).all()


def create_room(db: Session, data: RoomCreate) -> Room:
    campus = get_campus(db, data.campus_id)
    if not campus:
        raise ValueError("院区不存在")

    existing = (
        db.query(Room)
        .filter(Room.campus_id == data.campus_id, Room.code == data.code)
        .first()
    )
    if existing:
        raise ValueError("该院区诊室编码已存在")

    room = Room(**data.model_dump())
    db.add(room)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ValueError("该院区诊室编码已存在")
    db.refresh(room)
    return room


def get_room(db: Session, room_id: int) -> Room | None:
    return db.get(Room, room_id)


def list_rooms(
    db: Session, campus_id: int | None = None, department_id: int | None = None
) -> list[Room]:
    query = db.query(Room)
    if campus_id is not None:
        query = query.filter(Room.campus_id == campus_id)
    if department_id is not None:
        query = query.filter(Room.department_id == department_id)
    return query.order_by(Room.campus_id, Room.code).all()
