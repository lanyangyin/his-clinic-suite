from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.modules.auth.security import require_role

from .schemas import (
    DecoctRequest,
    DecoctionResponse,
    HerbCreate,
    HerbResponse,
    IssueRequest,
    PackageRequest,
    PrescriptionCreate,
    PrescriptionResponse,
    SoakRequest,
)
from .service import (
    create_herb,
    create_prescription,
    decoct,
    dispense_prescription,
    get_decoction,
    get_prescription,
    issue,
    list_decoctions,
    list_herbs,
    list_prescriptions,
    package,
    review_prescription,
    soak,
)

router = APIRouter(prefix="/tcm", tags=["tcm"])


@router.post("/herbs", response_model=HerbResponse, status_code=201)
def new_herb(
    data: HerbCreate,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("admin")),
):
    try:
        return create_herb(db, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/herbs", response_model=list[HerbResponse])
def herbs(db: Session = Depends(get_db)):
    return list_herbs(db)


@router.post(
    "/encounters/{encounter_id}/prescriptions",
    response_model=PrescriptionResponse,
    status_code=201,
)
def new_prescription(
    encounter_id: int,
    data: PrescriptionCreate,
    db: Session = Depends(get_db),
    user=Depends(require_role("doctor")),
):
    try:
        return create_prescription(db, encounter_id, data, user.username)
    except ValueError as e:
        code = 404 if str(e) == "就诊记录不存在" else 400
        raise HTTPException(status_code=code, detail=str(e))


@router.get("/prescriptions")
def prescriptions(
    status: str | None = None,
    encounter_id: int | None = None,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("doctor", "pharmacist")),
):
    return list_prescriptions(db, status, encounter_id)


@router.get("/prescriptions/{prescription_id}")
def prescription_detail(
    prescription_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("doctor", "pharmacist")),
):
    prescription = get_prescription(db, prescription_id)
    if not prescription:
        raise HTTPException(status_code=404, detail="中药处方不存在")
    return prescription


@router.post("/prescriptions/{prescription_id}/review", response_model=PrescriptionResponse)
def review(
    prescription_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_role("pharmacist")),
):
    try:
        return review_prescription(db, prescription_id, user.username)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/prescriptions/{prescription_id}/dispense", response_model=PrescriptionResponse)
def dispense(
    prescription_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_role("pharmacist")),
):
    try:
        return dispense_prescription(db, prescription_id, user.username)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/decoction-orders")
def decoction_orders(
    status: str | None = None,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("pharmacist", "decoction")),
):
    return list_decoctions(db, status)


@router.get("/decoction-orders/{order_id}", response_model=DecoctionResponse)
def decoction_detail(
    order_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("pharmacist", "decoction")),
):
    order = get_decoction(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="煎药单不存在")
    return order


@router.post("/decoction-orders/{order_id}/soak", response_model=DecoctionResponse)
def soak_order(
    order_id: int,
    data: SoakRequest,
    db: Session = Depends(get_db),
    user=Depends(require_role("pharmacist", "decoction")),
):
    try:
        return soak(db, order_id, data, user.username)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/decoction-orders/{order_id}/decoct", response_model=DecoctionResponse)
def decoct_order(
    order_id: int,
    data: DecoctRequest,
    db: Session = Depends(get_db),
    user=Depends(require_role("pharmacist", "decoction")),
):
    try:
        return decoct(db, order_id, data, user.username)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/decoction-orders/{order_id}/package", response_model=DecoctionResponse)
def package_order(
    order_id: int,
    data: PackageRequest,
    db: Session = Depends(get_db),
    user=Depends(require_role("pharmacist", "decoction")),
):
    try:
        return package(db, order_id, data, user.username)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/decoction-orders/{order_id}/issue", response_model=DecoctionResponse)
def issue_order(
    order_id: int,
    data: IssueRequest,
    db: Session = Depends(get_db),
    user=Depends(require_role("pharmacist", "decoction")),
):
    try:
        return issue(db, order_id, data, user.username)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
