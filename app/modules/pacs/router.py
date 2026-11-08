from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.modules.auth.security import require_role

from .schemas import (
    ImagingItemCreate,
    ImagingItemResponse,
    ImagingReportRequest,
    ImagingRequestCreate,
    ImagingRequestResponse,
)
from .service import (
    create_item,
    create_request,
    get_item,
    get_request,
    list_items,
    list_requests,
    report_request,
)

router = APIRouter(prefix="/pacs", tags=["pacs"])


@router.post("/items/", response_model=ImagingItemResponse, status_code=201)
def new_item(
    data: ImagingItemCreate,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("admin")),
):
    try:
        return create_item(db, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/items/", response_model=list[ImagingItemResponse])
def get_items(db: Session = Depends(get_db)):
    return list_items(db)


@router.get("/items/{item_id}", response_model=ImagingItemResponse)
def get_item_one(item_id: int, db: Session = Depends(get_db)):
    item = get_item(db, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="检查项目不存在")
    return item


@router.post(
    "/encounters/{encounter_id}/imaging-requests",
    response_model=ImagingRequestResponse,
    status_code=201,
)
def new_request(
    encounter_id: int,
    data: ImagingRequestCreate,
    db: Session = Depends(get_db),
    user=Depends(require_role("doctor")),
):
    try:
        return create_request(db, encounter_id, data, user.username)
    except ValueError as e:
        code = 404 if str(e) == "就诊记录不存在" else 400
        raise HTTPException(status_code=code, detail=str(e))


@router.get(
    "/encounters/{encounter_id}/imaging-requests",
    response_model=list[ImagingRequestResponse],
)
def get_encounter_requests(encounter_id: int, db: Session = Depends(get_db)):
    return list_requests(db, encounter_id)


@router.get("/requests/{request_id}", response_model=ImagingRequestResponse)
def get_request_one(request_id: int, db: Session = Depends(get_db)):
    request = get_request(db, request_id)
    if not request:
        raise HTTPException(status_code=404, detail="检查申请不存在")
    return request


@router.post("/requests/{request_id}/report", response_model=ImagingRequestResponse)
def report(
    request_id: int,
    data: ImagingReportRequest,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("radiology")),
):
    try:
        return report_request(db, request_id, data.report, data.image_url)
    except ValueError as e:
        code = 404 if str(e) == "检查申请不存在" else 400
        raise HTTPException(status_code=code, detail=str(e))
