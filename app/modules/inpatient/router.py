from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.modules.auth.security import require_role

from .schemas import (
    AdmissionCreate,
    AdmissionResponse,
    BedCreate,
    BedResponse,
    BillResponse,
    ChargeResponse,
    DispenseRequestResponse,
    ExecuteRequest,
    ExecutionResponse,
    NursingNoteCreate,
    NursingNoteResponse,
    OrderCreate,
    OrderResponse,
    TransferBedRequest,
    VitalSignCreate,
    VitalSignResponse,
    WardCreate,
    WardResponse,
)
from .service import (
    create_admission,
    create_bed,
    create_dispense_request,
    create_nursing_note,
    create_order,
    create_ward,
    discharge,
    dispense_request,
    execute_order,
    get_admission,
    get_bed,
    get_bill,
    get_charges,
    get_dispense_request,
    get_order,
    get_ward,
    list_admissions,
    list_beds,
    list_dispense_requests,
    list_nursing_notes,
    list_orders,
    list_vital_signs,
    list_wards,
    record_vital_signs,
    return_dispense,
    stop_order,
    transfer_bed,
)

router = APIRouter(tags=["inpatient"])


@router.post("/wards/", response_model=WardResponse, status_code=201)
def new_ward(
    data: WardCreate,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("admin")),
):
    return create_ward(db, data)


@router.get("/wards/", response_model=list[WardResponse])
def get_all_wards(db: Session = Depends(get_db)):
    return list_wards(db)


@router.get("/admissions/", response_model=list[AdmissionResponse])
def get_all_admissions(
    status: str | None = None,
    doctor_id: int | None = None,
    db: Session = Depends(get_db),
):
    return list_admissions(db, status, doctor_id)


@router.get("/wards/{ward_id}", response_model=WardResponse)
def get_ward_one(ward_id: int, db: Session = Depends(get_db)):
    ward = get_ward(db, ward_id)
    if not ward:
        raise HTTPException(status_code=404, detail="病区不存在")
    return ward


@router.get("/wards/{ward_id}/beds", response_model=list[BedResponse])
def get_ward_beds(ward_id: int, db: Session = Depends(get_db)):
    if not get_ward(db, ward_id):
        raise HTTPException(status_code=404, detail="病区不存在")
    return list_beds(db, ward_id)


@router.post("/beds/", response_model=BedResponse, status_code=201)
def new_bed(
    data: BedCreate,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("admin")),
):
    try:
        return create_bed(db, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/beds/{bed_id}", response_model=BedResponse)
def get_bed_one(bed_id: int, db: Session = Depends(get_db)):
    bed = get_bed(db, bed_id)
    if not bed:
        raise HTTPException(status_code=404, detail="床位不存在")
    return bed


@router.post("/admissions/", response_model=AdmissionResponse, status_code=201)
def admit(
    data: AdmissionCreate,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("cashier")),
):
    try:
        return create_admission(db, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/admissions/{admission_id}", response_model=AdmissionResponse)
def get_admission_one(admission_id: int, db: Session = Depends(get_db)):
    admission = get_admission(db, admission_id)
    if not admission:
        raise HTTPException(status_code=404, detail="住院记录不存在")
    return admission


@router.post(
    "/admissions/{admission_id}/transfer-bed", response_model=AdmissionResponse
)
def transfer(
    admission_id: int,
    data: TransferBedRequest,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("doctor")),
):
    try:
        return transfer_bed(db, admission_id, data.bed_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/admissions/{admission_id}/discharge", response_model=AdmissionResponse)
def discharge_patient(
    admission_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("doctor")),
):
    try:
        return discharge(db, admission_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/admissions/{admission_id}/orders", response_model=OrderResponse, status_code=201
)
def new_order(
    admission_id: int,
    data: OrderCreate,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("doctor")),
):
    try:
        return create_order(db, admission_id, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/admissions/{admission_id}/orders", response_model=list[OrderResponse])
def get_admission_orders(admission_id: int, db: Session = Depends(get_db)):
    if not get_admission(db, admission_id):
        raise HTTPException(status_code=404, detail="住院记录不存在")
    return list_orders(db, admission_id)


@router.get("/orders/{order_id}", response_model=OrderResponse)
def get_order_one(order_id: int, db: Session = Depends(get_db)):
    order = get_order(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="医嘱不存在")
    return order


@router.post("/orders/{order_id}/stop", response_model=OrderResponse)
def stop(
    order_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("doctor")),
):
    try:
        return stop_order(db, order_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/orders/{order_id}/execute", response_model=ExecutionResponse, status_code=201
)
def execute(
    order_id: int,
    data: ExecuteRequest,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("nurse")),
):
    try:
        return execute_order(db, order_id, data.note)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "/admissions/{admission_id}/charges", response_model=list[ChargeResponse]
)
def get_admission_charges(admission_id: int, db: Session = Depends(get_db)):
    if not get_admission(db, admission_id):
        raise HTTPException(status_code=404, detail="住院记录不存在")
    return get_charges(db, admission_id)


@router.get("/admissions/{admission_id}/bill", response_model=BillResponse)
def get_admission_bill(admission_id: int, db: Session = Depends(get_db)):
    if not get_admission(db, admission_id):
        raise HTTPException(status_code=404, detail="住院记录不存在")
    return get_bill(db, admission_id)


@router.post(
    "/orders/{order_id}/dispense-request",
    response_model=DispenseRequestResponse,
    status_code=201,
)
def new_dispense_request(
    order_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("nurse")),
):
    try:
        return create_dispense_request(db, order_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "/admissions/{admission_id}/dispense-requests",
    response_model=list[DispenseRequestResponse],
)
def get_admission_dispense_requests(admission_id: int, db: Session = Depends(get_db)):
    if not get_admission(db, admission_id):
        raise HTTPException(status_code=404, detail="住院记录不存在")
    return list_dispense_requests(db, admission_id)


@router.get("/dispense-requests/{request_id}", response_model=DispenseRequestResponse)
def get_dispense_request_one(request_id: int, db: Session = Depends(get_db)):
    request = get_dispense_request(db, request_id)
    if not request:
        raise HTTPException(status_code=404, detail="摆药单不存在")
    return request


@router.post(
    "/dispense-requests/{request_id}/dispense",
    response_model=DispenseRequestResponse,
)
def dispense(
    request_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("pharmacist")),
):
    try:
        return dispense_request(db, request_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/dispense-requests/{request_id}/return",
    response_model=DispenseRequestResponse,
)
def return_dispensed(
    request_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("pharmacist")),
):
    try:
        return return_dispense(db, request_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/admissions/{admission_id}/vital-signs",
    response_model=VitalSignResponse,
    status_code=201,
)
def new_vital_signs(
    admission_id: int,
    data: VitalSignCreate,
    db: Session = Depends(get_db),
    user=Depends(require_role("nurse")),
):
    try:
        return record_vital_signs(db, admission_id, data, user.username)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "/admissions/{admission_id}/vital-signs",
    response_model=list[VitalSignResponse],
)
def get_admission_vital_signs(admission_id: int, db: Session = Depends(get_db)):
    if not get_admission(db, admission_id):
        raise HTTPException(status_code=404, detail="住院记录不存在")
    return list_vital_signs(db, admission_id)


@router.post(
    "/admissions/{admission_id}/nursing-notes",
    response_model=NursingNoteResponse,
    status_code=201,
)
def new_nursing_note(
    admission_id: int,
    data: NursingNoteCreate,
    db: Session = Depends(get_db),
    user=Depends(require_role("nurse")),
):
    try:
        return create_nursing_note(db, admission_id, data, user.username)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "/admissions/{admission_id}/nursing-notes",
    response_model=list[NursingNoteResponse],
)
def get_admission_nursing_notes(admission_id: int, db: Session = Depends(get_db)):
    if not get_admission(db, admission_id):
        raise HTTPException(status_code=404, detail="住院记录不存在")
    return list_nursing_notes(db, admission_id)
