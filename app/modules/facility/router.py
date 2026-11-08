from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.modules.auth.security import require_role

from .schemas import CampusCreate, CampusResponse, RoomCreate, RoomResponse
from .service import (
    create_campus,
    create_room,
    get_campus,
    get_room,
    list_campuses,
    list_rooms,
)

router = APIRouter(tags=["facility"])


@router.post("/campuses/", response_model=CampusResponse, status_code=201)
def new_campus(
    data: CampusCreate,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("admin")),
):
    try:
        return create_campus(db, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/campuses/", response_model=list[CampusResponse])
def get_campuses(db: Session = Depends(get_db)):
    return list_campuses(db)


@router.get("/campuses/{campus_id}", response_model=CampusResponse)
def get_one_campus(campus_id: int, db: Session = Depends(get_db)):
    campus = get_campus(db, campus_id)
    if not campus:
        raise HTTPException(status_code=404, detail="院区不存在")
    return campus


@router.post("/rooms/", response_model=RoomResponse, status_code=201)
def new_room(
    data: RoomCreate,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("admin")),
):
    try:
        return create_room(db, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/rooms/", response_model=list[RoomResponse])
def get_rooms(
    campus_id: int | None = None,
    department_id: int | None = None,
    db: Session = Depends(get_db),
):
    return list_rooms(db, campus_id, department_id)


@router.get("/rooms/{room_id}", response_model=RoomResponse)
def get_one_room(room_id: int, db: Session = Depends(get_db)):
    room = get_room(db, room_id)
    if not room:
        raise HTTPException(status_code=404, detail="诊室不存在")
    return room
