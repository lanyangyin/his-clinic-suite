from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.modules.auth.security import require_role

from .schemas import (
    CompleteRequest,
    NursingOrderResponse,
    ObserveRequest,
    ObservationResponse,
    PrepareRequest,
    PreparationResponse,
    SkipRequest,
    StartRequest,
)
from .service import (
    complete,
    detail,
    get_order,
    list_orders,
    observe,
    prepare,
    skip,
    start,
    sync_orders,
)

router = APIRouter(prefix="/nursing", tags=["nursing"])


@router.post("/encounters/{encounter_id}/sync", response_model=list[NursingOrderResponse])
def sync(
    encounter_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("nurse")),
):
    try:
        return sync_orders(db, encounter_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/orders")
def orders(
    status: str | None = None,
    encounter_id: int | None = None,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("nurse")),
):
    return list_orders(db, status, encounter_id)


@router.get("/orders/{order_id}/detail")
def order_detail(
    order_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("nurse")),
):
    try:
        return detail(db, order_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/orders/{order_id}/prepare", response_model=PreparationResponse, status_code=201)
def prepare_order(
    order_id: int,
    data: PrepareRequest,
    db: Session = Depends(get_db),
    user=Depends(require_role("nurse")),
):
    try:
        return prepare(db, order_id, data, user.username)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/orders/{order_id}/start", response_model=NursingOrderResponse)
def start_order(
    order_id: int,
    data: StartRequest,
    db: Session = Depends(get_db),
    user=Depends(require_role("nurse")),
):
    try:
        return start(db, order_id, data, user.username)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/orders/{order_id}/observe", response_model=ObservationResponse, status_code=201)
def observe_order(
    order_id: int,
    data: ObserveRequest,
    db: Session = Depends(get_db),
    user=Depends(require_role("nurse")),
):
    try:
        return observe(db, order_id, data, user.username)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/orders/{order_id}/complete", response_model=NursingOrderResponse)
def complete_order(
    order_id: int,
    data: CompleteRequest,
    db: Session = Depends(get_db),
    user=Depends(require_role("nurse")),
):
    try:
        return complete(db, order_id, data, user.username)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/orders/{order_id}/skip", response_model=NursingOrderResponse)
def skip_order(
    order_id: int,
    data: SkipRequest,
    db: Session = Depends(get_db),
    user=Depends(require_role("nurse")),
):
    try:
        return skip(db, order_id, data, user.username)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
