from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.modules.auth.security import require_role

from .schemas import (
    InventoryPreviewResponse,
    PeriodRequest,
    UploadDetail,
    UploadResponse,
)
from .service import create_upload, get_upload, list_uploads, preview

router = APIRouter(prefix="/insurance/inventory", tags=["insurance-inventory"])


@router.post("/preview", response_model=InventoryPreviewResponse)
def preview_inventory(
    data: PeriodRequest,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("admin")),
):
    try:
        result = preview(db, data.start_date, data.end_date)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return result


@router.post("/upload", response_model=UploadResponse)
def upload_inventory(
    data: PeriodRequest,
    db: Session = Depends(get_db),
    user=Depends(require_role("admin")),
):
    try:
        return create_upload(db, data.start_date, data.end_date, created_by=user.username)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/uploads", response_model=list[UploadResponse])
def get_uploads(
    limit: int = 50,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("admin")),
):
    return list_uploads(db, limit)


@router.get("/uploads/{upload_id}", response_model=UploadDetail)
def get_upload_detail(
    upload_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("admin")),
):
    upload = get_upload(db, upload_id)
    if not upload:
        raise HTTPException(status_code=404, detail="上传记录不存在")
    return upload
