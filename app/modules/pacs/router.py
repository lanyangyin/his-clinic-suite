from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.modules.auth.security import require_read_login, require_role

from .schemas import (
    ImagingItemCreate,
    ImagingItemResponse,
    ImagingReportRequest,
    ImagingRequestCreate,
    ImagingReviewRequest,
    ImagingTemplateCreate,
    ImagingTemplateResponse,
    ImagingRequestResponse,
)
from .service import (
    create_item,
    list_worklist,
    create_request,
    get_item,
    get_request,
    list_items,
    list_requests,
    report_request,
    review_request,
    create_template,
    list_templates,
)

router = APIRouter(prefix="/pacs", tags=["pacs"], dependencies=[Depends(require_read_login)])


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


@router.get("/templates", response_model=list[ImagingTemplateResponse])
def get_templates(db: Session = Depends(get_db)):
    return list_templates(db)


@router.post("/templates", response_model=ImagingTemplateResponse, status_code=201)
def new_template(
    data: ImagingTemplateCreate,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("admin")),
):
    try:
        return create_template(db, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/worklist")
def worklist(
    status: str = "pending",
    priority: str | None = None,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("radiology", "admin")),
):
    return list_worklist(db, status, priority)


@router.post("/requests/{request_id}/review", response_model=ImagingRequestResponse)
def review(
    request_id: int,
    data: ImagingReviewRequest,
    db: Session = Depends(get_db),
    user=Depends(require_role("radiology", "admin")),
):
    try:
        return review_request(db, request_id, data.approve, user.username, data.note)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


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
    user=Depends(require_role("radiology")),
):
    try:
        return report_request(
            db,
            request_id,
            data.report,
            data.image_url,
            reported_by=user.username,
            findings=data.findings,
            impression=data.impression,
            template_name=data.template_name,
            study_uid=data.study_uid,
            series_uid=data.series_uid,
            modality=data.modality,
        )
    except ValueError as e:
        code = 404 if str(e) == "检查申请不存在" else 400
        raise HTTPException(status_code=code, detail=str(e))
