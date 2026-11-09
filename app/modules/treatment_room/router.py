from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.modules.auth.security import require_role

from .schemas import (
    CaseCreate,
    CaseResponse,
    CompleteRequest,
    RoomCreate,
    RoomResponse,
    StartRequest,
)
from .service import (
    cancel_case,
    complete_case,
    create_case,
    create_room,
    get_case,
    list_cases,
    list_rooms,
    start_case,
)

router = APIRouter(prefix="/treatment-room", tags=["treatment-room"])


@router.post("/rooms", response_model=RoomResponse, status_code=201)
def new_room(
    data: RoomCreate,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("treatment")),
):
    try:
        return create_room(db, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/rooms", response_model=list[RoomResponse])
def rooms(
    db: Session = Depends(get_db),
    _: None = Depends(require_role("treatment")),
):
    return list_rooms(db)


@router.post("/cases", response_model=CaseResponse, status_code=201)
def new_case(
    data: CaseCreate,
    db: Session = Depends(get_db),
    user=Depends(require_role("treatment")),
):
    try:
        return create_case(db, data, user.username)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/cases")
def cases(
    status: str | None = None,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("treatment")),
):
    return list_cases(db, status)


@router.get("/cases/{case_id}", response_model=CaseResponse)
def case_detail(
    case_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("treatment")),
):
    case = get_case(db, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="治疗室病例不存在")
    return case


@router.post("/cases/{case_id}/start", response_model=CaseResponse)
def start(
    case_id: int,
    data: StartRequest,
    db: Session = Depends(get_db),
    user=Depends(require_role("treatment")),
):
    try:
        return start_case(db, case_id, data, user.username)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/cases/{case_id}/complete", response_model=CaseResponse)
def complete(
    case_id: int,
    data: CompleteRequest,
    db: Session = Depends(get_db),
    user=Depends(require_role("treatment")),
):
    try:
        return complete_case(db, case_id, data, user.username)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/cases/{case_id}/cancel", response_model=CaseResponse)
def cancel(
    case_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_role("treatment")),
):
    try:
        return cancel_case(db, case_id, user.username)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
