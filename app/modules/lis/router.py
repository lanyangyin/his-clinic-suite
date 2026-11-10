from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.modules.auth.security import require_role

from .schemas import (
    CriticalAckRequest,
    CriticalRequest,
    LabItemCreate,
    LabItemResponse,
    LabReportRequest,
    LabRequestCreate,
    LabRequestResponse,
    RejectRequest,
    SpecimenActionRequest,
)
from .service import (
    acknowledge_critical,
    collect_request,
    create_item,
    create_request,
    critical_alerts,
    get_item,
    get_request,
    list_items,
    list_requests,
    receive_request,
    register_critical,
    reject_request,
    report_request,
    review_request,
    start_testing,
    worklist,
)

router = APIRouter(prefix="/lab", tags=["lis"])


@router.post("/items/", response_model=LabItemResponse, status_code=201)
def new_item(
    data: LabItemCreate,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("admin")),
):
    try:
        return create_item(db, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/items/", response_model=list[LabItemResponse])
def get_items(db: Session = Depends(get_db)):
    return list_items(db)


@router.get("/items/{item_id}", response_model=LabItemResponse)
def get_item_one(item_id: int, db: Session = Depends(get_db)):
    item = get_item(db, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="检验项目不存在")
    return item


@router.post(
    "/encounters/{encounter_id}/lab-requests",
    response_model=LabRequestResponse,
    status_code=201,
)
def new_request(
    encounter_id: int,
    data: LabRequestCreate,
    db: Session = Depends(get_db),
    user=Depends(require_role("doctor")),
):
    try:
        return create_request(db, encounter_id, data, user.username)
    except ValueError as e:
        code = 404 if str(e) == "就诊记录不存在" else 400
        raise HTTPException(status_code=code, detail=str(e))


@router.get(
    "/encounters/{encounter_id}/lab-requests",
    response_model=list[LabRequestResponse],
)
def get_encounter_requests(encounter_id: int, db: Session = Depends(get_db)):
    return list_requests(db, encounter_id)


@router.get("/requests/{request_id}", response_model=LabRequestResponse)
def get_request_one(request_id: int, db: Session = Depends(get_db)):
    request = get_request(db, request_id)
    if not request:
        raise HTTPException(status_code=404, detail="检验申请不存在")
    return request


@router.get("/critical-alerts")
def get_critical_alerts(
    db: Session = Depends(get_db),
    _: None = Depends(require_role("doctor")),
):
    """医生工作台：未确认的危急值。"""
    return critical_alerts(db)


@router.get("/worklist")
def get_worklist(
    status: str | None = None,
    priority: str | None = None,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("lab")),
):
    """检验科工作列表（可按状态/加急筛选）。"""
    return worklist(db, status, priority)


@router.post("/requests/{request_id}/collect", response_model=LabRequestResponse)
def collect(
    request_id: int,
    data: SpecimenActionRequest | None = None,
    db: Session = Depends(get_db),
    user=Depends(require_role("nurse", "lab")),
):
    try:
        return collect_request(db, request_id, data or SpecimenActionRequest(), user.username)
    except ValueError as e:
        code = 404 if str(e) == "检验申请不存在" else 400
        raise HTTPException(status_code=code, detail=str(e))


@router.post("/requests/{request_id}/receive", response_model=LabRequestResponse)
def receive(
    request_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_role("lab")),
):
    try:
        return receive_request(db, request_id, user.username)
    except ValueError as e:
        code = 404 if str(e) == "检验申请不存在" else 400
        raise HTTPException(status_code=code, detail=str(e))


@router.post("/requests/{request_id}/reject", response_model=LabRequestResponse)
def reject(
    request_id: int,
    data: RejectRequest,
    db: Session = Depends(get_db),
    user=Depends(require_role("lab")),
):
    try:
        return reject_request(db, request_id, data, user.username)
    except ValueError as e:
        code = 404 if str(e) == "检验申请不存在" else 400
        raise HTTPException(status_code=code, detail=str(e))


@router.post("/requests/{request_id}/start", response_model=LabRequestResponse)
def start(
    request_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_role("lab")),
):
    try:
        return start_testing(db, request_id, user.username)
    except ValueError as e:
        code = 404 if str(e) == "检验申请不存在" else 400
        raise HTTPException(status_code=code, detail=str(e))


@router.post("/requests/{request_id}/review", response_model=LabRequestResponse)
def review(
    request_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_role("lab")),
):
    try:
        return review_request(db, request_id, user.username)
    except ValueError as e:
        code = 404 if str(e) == "检验申请不存在" else 400
        raise HTTPException(status_code=code, detail=str(e))


@router.post(
    "/requests/{request_id}/critical-ack", response_model=LabRequestResponse
)
def critical_ack(
    request_id: int,
    data: CriticalAckRequest,
    db: Session = Depends(get_db),
    user=Depends(require_role("doctor")),
):
    try:
        return acknowledge_critical(db, request_id, data.note, user.username)
    except ValueError as e:
        code = 404 if str(e) == "检验申请不存在" else 400
        raise HTTPException(status_code=code, detail=str(e))


@router.post("/requests/{request_id}/critical", response_model=LabRequestResponse)
def critical(
    request_id: int,
    data: CriticalRequest,
    db: Session = Depends(get_db),
    user=Depends(require_role("lab")),
):
    try:
        return register_critical(db, request_id, data, user.username)
    except ValueError as e:
        code = 404 if str(e) == "检验申请不存在" else 400
        raise HTTPException(status_code=code, detail=str(e))


@router.post("/requests/{request_id}/report", response_model=LabRequestResponse)
def report(
    request_id: int,
    data: LabReportRequest,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("lab")),
):
    try:
        return report_request(db, request_id, data)
    except ValueError as e:
        code = 404 if str(e) == "检验申请不存在" else 400
        raise HTTPException(status_code=code, detail=str(e))
