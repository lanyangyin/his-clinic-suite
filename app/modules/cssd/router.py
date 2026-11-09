from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.modules.auth.security import require_role

from .schemas import (
    BatchCreate,
    BatchResponse,
    IssueRequest,
    PackageCreate,
    PackageRecallRequest,
    PackageResponse,
    RejectRequest,
    ReleaseRequest,
    SetCreate,
    SetResponse,
    UsageResponse,
    UseRequest,
)
from .service import (
    create_batch,
    create_package,
    create_set,
    expiry_alerts,
    get_batch,
    get_package,
    issue_package,
    list_batches,
    list_packages,
    list_sets,
    recall_package,
    reject_batch,
    release_batch,
    use_package,
)

router = APIRouter(prefix="/cssd", tags=["cssd"])


@router.post("/sets", response_model=SetResponse, status_code=201)
def new_set(
    data: SetCreate,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("nurse", "warehouse")),
):
    try:
        return create_set(db, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/sets", response_model=list[SetResponse])
def sets(
    db: Session = Depends(get_db),
    _: None = Depends(require_role("nurse", "warehouse")),
):
    return list_sets(db)


@router.post("/batches", response_model=BatchResponse, status_code=201)
def new_batch(
    data: BatchCreate,
    db: Session = Depends(get_db),
    user=Depends(require_role("nurse", "warehouse")),
):
    try:
        batch = create_batch(db, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not batch.operator:
        batch.operator = user.username
        db.commit()
    return batch


@router.get("/batches", response_model=list[BatchResponse])
def batches(
    release_status: str | None = None,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("nurse", "warehouse")),
):
    return list_batches(db, release_status)


@router.post("/batches/{batch_id}/release", response_model=BatchResponse)
def release(
    batch_id: int,
    data: ReleaseRequest,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("nurse", "warehouse")),
):
    try:
        return release_batch(db, batch_id, data.released_by)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/batches/{batch_id}/reject", response_model=BatchResponse)
def reject(
    batch_id: int,
    data: RejectRequest,
    db: Session = Depends(get_db),
    user=Depends(require_role("nurse", "warehouse")),
):
    try:
        return reject_batch(db, batch_id, data.reason, user.username)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/packages", response_model=PackageResponse, status_code=201)
def new_package(
    data: PackageCreate,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("nurse", "warehouse")),
):
    try:
        return create_package(db, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/packages", response_model=list[PackageResponse])
def packages(
    status: str | None = None,
    set_id: int | None = None,
    batch_id: int | None = None,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("nurse", "warehouse")),
):
    return list_packages(db, status, set_id, batch_id)


@router.post("/packages/{package_id}/issue", response_model=PackageResponse)
def issue(
    package_id: int,
    data: IssueRequest,
    db: Session = Depends(get_db),
    user=Depends(require_role("nurse", "warehouse")),
):
    try:
        return issue_package(db, package_id, data, user.username)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/packages/{package_id}/use", response_model=UsageResponse, status_code=201)
def use(
    package_id: int,
    data: UseRequest,
    db: Session = Depends(get_db),
    user=Depends(require_role("nurse", "warehouse")),
):
    try:
        return use_package(db, package_id, data, user.username)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/packages/{package_id}/recall", response_model=PackageResponse)
def recall(
    package_id: int,
    data: PackageRecallRequest,
    db: Session = Depends(get_db),
    user=Depends(require_role("nurse", "warehouse")),
):
    try:
        return recall_package(db, package_id, data.reason, user.username)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/expiry-alerts", response_model=list[PackageResponse])
def alerts(
    days: int = 30,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("nurse", "warehouse")),
):
    return expiry_alerts(db, days)
