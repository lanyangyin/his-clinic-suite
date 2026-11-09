from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.modules.auth.security import require_role

from .schemas import (
    CaseCreate,
    CaseResponse,
    CountCreate,
    CountResponse,
    RecordCreate,
    RecordResponse,
    RecoveryCreate,
    RecoveryResponse,
    RoomCreate,
    RoomResponse,
    SafetyCreate,
    SafetyResponse,
)
from .service import (
    add_count,
    add_record,
    add_recovery,
    add_safety,
    attach_package,
    complete_case,
    create_case,
    create_room,
    detail,
    get_case,
    list_cases,
    list_rooms,
    start_case,
)

router = APIRouter(prefix="/surgery", tags=["surgery"])


@router.post("/rooms", response_model=RoomResponse, status_code=201)
def new_room(
    data: RoomCreate,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("surgery")),
):
    try:
        return create_room(db, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/rooms", response_model=list[RoomResponse])
def rooms(
    db: Session = Depends(get_db),
    _: None = Depends(require_role("surgery")),
):
    return list_rooms(db)


@router.post("/cases", response_model=CaseResponse, status_code=201)
def new_case(
    data: CaseCreate,
    db: Session = Depends(get_db),
    user=Depends(require_role("surgery")),
):
    try:
        return create_case(db, data, user.username)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/cases")
def cases(
    status: str | None = None,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("surgery")),
):
    return list_cases(db, status)


@router.get("/cases/{case_id}")
def case_detail(
    case_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("surgery")),
):
    data = detail(db, case_id)
    if not data:
        raise HTTPException(status_code=404, detail="手术不存在")
    return data


@router.post("/cases/{case_id}/safety", response_model=SafetyResponse, status_code=201)
def safety(
    case_id: int,
    data: SafetyCreate,
    db: Session = Depends(get_db),
    user=Depends(require_role("surgery")),
):
    try:
        return add_safety(db, case_id, data, user.username)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/cases/{case_id}/start", response_model=CaseResponse)
def start(
    case_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_role("surgery")),
):
    try:
        return start_case(db, case_id, user.username)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/cases/{case_id}/record", response_model=RecordResponse, status_code=201)
def record(
    case_id: int,
    data: RecordCreate,
    db: Session = Depends(get_db),
    user=Depends(require_role("surgery")),
):
    try:
        return add_record(db, case_id, data, user.username)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/cases/{case_id}/counts", response_model=CountResponse, status_code=201)
def counts(
    case_id: int,
    data: CountCreate,
    db: Session = Depends(get_db),
    user=Depends(require_role("surgery")),
):
    try:
        return add_count(db, case_id, data, user.username)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/cases/{case_id}/complete", response_model=CaseResponse)
def complete(
    case_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_role("surgery")),
):
    try:
        return complete_case(db, case_id, user.username)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/cases/{case_id}/recovery", response_model=RecoveryResponse, status_code=201)
def recovery(
    case_id: int,
    data: RecoveryCreate,
    db: Session = Depends(get_db),
    user=Depends(require_role("surgery")),
):
    try:
        return add_recovery(db, case_id, data, user.username)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/cases/{case_id}/packages/{package_id}")
def package(
    case_id: int,
    package_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_role("surgery")),
):
    try:
        return attach_package(db, case_id, package_id, user.username)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
