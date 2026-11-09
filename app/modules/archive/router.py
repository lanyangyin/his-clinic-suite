from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.modules.auth.security import require_role

from .schemas import (
    ArchiveCompleteRequest,
    ArchiveRecordCreate,
    ArchiveRecordResponse,
    BorrowCreate,
    BorrowResponse,
    CopyCompleteRequest,
    CopyCreate,
    CopyResponse,
    DestroyCreate,
    SealCreate,
    SealResponse,
)
from .service import (
    archive_record,
    borrow_record,
    complete_copy,
    create_copy,
    create_record,
    destroy_record,
    get_record,
    history,
    list_records,
    return_borrowing,
    seal_record,
    unseal_record,
)

router = APIRouter(prefix="/archive", tags=["archive"])


@router.post("/records", response_model=ArchiveRecordResponse, status_code=201)
def new_record(
    data: ArchiveRecordCreate,
    db: Session = Depends(get_db),
    user=Depends(require_role("archive")),
):
    try:
        return create_record(db, data, user.username)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/records", response_model=list[ArchiveRecordResponse])
def records(
    archive_no: str | None = None,
    patient_id: int | None = None,
    status: str | None = None,
    record_type: str | None = None,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("archive", "doctor")),
):
    return list_records(db, archive_no, patient_id, status, record_type)


@router.get("/records/{record_id}", response_model=ArchiveRecordResponse)
def record_detail(
    record_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("archive", "doctor")),
):
    record = get_record(db, record_id)
    if not record:
        raise HTTPException(status_code=404, detail="病案不存在")
    return record


@router.get("/records/{record_id}/history")
def record_history(
    record_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("archive")),
):
    try:
        return history(db, record_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/records/{record_id}/archive", response_model=ArchiveRecordResponse)
def archive(
    record_id: int,
    data: ArchiveCompleteRequest,
    db: Session = Depends(get_db),
    user=Depends(require_role("archive")),
):
    try:
        return archive_record(db, record_id, data, user.username)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/records/{record_id}/borrow", response_model=BorrowResponse, status_code=201)
def borrow(
    record_id: int,
    data: BorrowCreate,
    db: Session = Depends(get_db),
    user=Depends(require_role("archive")),
):
    try:
        return borrow_record(db, record_id, data, user.username)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/borrowings/{borrowing_id}/return", response_model=BorrowResponse)
def do_return(
    borrowing_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_role("archive")),
):
    try:
        return return_borrowing(db, borrowing_id, user.username)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/records/{record_id}/copy", response_model=CopyResponse, status_code=201)
def copy(
    record_id: int,
    data: CopyCreate,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("archive")),
):
    try:
        return create_copy(db, record_id, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/copies/{copy_id}/complete", response_model=CopyResponse)
def copy_complete(
    copy_id: int,
    data: CopyCompleteRequest,
    db: Session = Depends(get_db),
    user=Depends(require_role("archive")),
):
    try:
        return complete_copy(db, copy_id, data, user.username)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/records/{record_id}/seal", response_model=SealResponse, status_code=201)
def seal(
    record_id: int,
    data: SealCreate,
    db: Session = Depends(get_db),
    user=Depends(require_role("archive")),
):
    try:
        return seal_record(db, record_id, data, user.username)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/records/{record_id}/unseal", response_model=SealResponse, status_code=201)
def unseal(
    record_id: int,
    data: SealCreate,
    db: Session = Depends(get_db),
    user=Depends(require_role("archive")),
):
    try:
        return unseal_record(db, record_id, data, user.username)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/records/{record_id}/destroy")
def destroy(
    record_id: int,
    data: DestroyCreate,
    db: Session = Depends(get_db),
    user=Depends(require_role("archive")),
):
    try:
        row = destroy_record(db, record_id, data, user.username)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"id": row.id, "record_id": row.record_id, "destroyed_at": row.destroyed_at}
