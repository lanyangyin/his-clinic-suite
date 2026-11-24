from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.modules.auth.security import require_read_login, require_role
from app.modules.patient.models import Patient
from app.modules.registration.models import Registration

from .schemas import TicketCreate, TicketResponse
from .service import (
    call_ticket,
    create_ticket,
    get_ticket,
    list_queue,
    pass_ticket,
)

router = APIRouter(prefix="/triage", tags=["triage"], dependencies=[Depends(require_read_login)])


@router.post("/tickets", response_model=TicketResponse, status_code=201)
def new_ticket(
    data: TicketCreate,
    db: Session = Depends(get_db),
    user=Depends(require_role("nurse")),
):
    try:
        return create_ticket(db, data, user.username)
    except ValueError as e:
        code = 404 if str(e) == "挂号记录不存在" else 400
        raise HTTPException(status_code=code, detail=str(e))


@router.get("/tickets/{ticket_id}", response_model=TicketResponse)
def get_ticket_one(ticket_id: int, db: Session = Depends(get_db)):
    ticket = get_ticket(db, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="叫号单不存在")
    return ticket


def _with_patient(db: Session, ticket) -> TicketResponse:
    reg = db.get(Registration, ticket.registration_id)
    patient = db.get(Patient, reg.patient_id) if reg else None
    return TicketResponse.model_validate(ticket).model_copy(
        update={
            "patient_name": patient.name if patient else "",
            "patient_no": patient.patient_no if patient else "",
            "doctor_id": reg.doctor_id if reg else None,
        }
    )


@router.get("/queue", response_model=list[TicketResponse])
def get_queue(status: str = "waiting", db: Session = Depends(get_db)):
    return [_with_patient(db, ticket) for ticket in list_queue(db, status)]


@router.post("/tickets/{ticket_id}/call", response_model=TicketResponse)
def call(
    ticket_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("nurse")),
):
    try:
        return call_ticket(db, ticket_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/tickets/{ticket_id}/pass", response_model=TicketResponse)
def pass_ticket_route(
    ticket_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("nurse")),
):
    try:
        return pass_ticket(db, ticket_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
