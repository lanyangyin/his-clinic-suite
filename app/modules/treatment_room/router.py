from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.modules.auth.security import require_role
from app.modules.procedure_materials.schemas import (
    ProcedureMaterialCreate,
    ProcedureMaterialResponse,
)

from .schemas import (
    CaseCreate,
    CaseResponse,
    CompleteRequest,
    FollowUpCreate,
    FollowUpResponse,
    RoomCreate,
    RoomResponse,
    StartRequest,
    TemplateConfigUpdate,
    TreatmentTemplate,
)
from .service import (
    add_material,
    cancel_case,
    cancel_followup,
    complete_case,
    complete_followup,
    create_case,
    create_followup,
    create_room,
    get_case,
    list_cases,
    list_followups,
    list_rooms,
    list_templates,
    report,
    set_template_config,
    start_case,
)

router = APIRouter(prefix="/treatment-room", tags=["treatment-room"])


@router.post("/rooms", response_model=RoomResponse, status_code=201)
def new_room(
    data: RoomCreate,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("treatment")),
):
    try:
        return create_room(db, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/rooms", response_model=list[RoomResponse])
def rooms(
    db: Session = Depends(get_db),
    _: None = Depends(require_role("treatment")),
):
    return list_rooms(db)


@router.post("/cases", response_model=CaseResponse, status_code=201)
def new_case(
    data: CaseCreate,
    db: Session = Depends(get_db),
    user=Depends(require_role("treatment")),
):
    try:
        return create_case(db, data, user.username)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/cases")
def cases(
    status: str | None = None,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("treatment")),
):
    return list_cases(db, status)


@router.get("/cases/{case_id}", response_model=CaseResponse)
def case_detail(
    case_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("treatment")),
):
    case = get_case(db, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="治疗室病例不存在")
    return case


@router.post("/cases/{case_id}/start", response_model=CaseResponse)
def start(
    case_id: int,
    data: StartRequest,
    db: Session = Depends(get_db),
    user=Depends(require_role("treatment")),
):
    try:
        return start_case(db, case_id, data, user.username)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/cases/{case_id}/complete", response_model=CaseResponse)
def complete(
    case_id: int,
    data: CompleteRequest,
    db: Session = Depends(get_db),
    user=Depends(require_role("treatment")),
):
    try:
        return complete_case(db, case_id, data, user.username)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/cases/{case_id}/cancel", response_model=CaseResponse)
def cancel(
    case_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_role("treatment")),
):
    try:
        return cancel_case(db, case_id, user.username)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/cases/{case_id}/materials", response_model=ProcedureMaterialResponse, status_code=201)
def material(
    case_id: int,
    data: ProcedureMaterialCreate,
    db: Session = Depends(get_db),
    user=Depends(require_role("treatment")),
):
    try:
        return add_material(db, case_id, data, user.username)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/templates", response_model=list[TreatmentTemplate])
def templates(
    db: Session = Depends(get_db),
    _: None = Depends(require_role("treatment")),
):
    return list_templates(db)


@router.put("/templates/{template_code}")
def configure_template(
    template_code: str,
    data: TemplateConfigUpdate,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("admin")),
):
    try:
        row = set_template_config(db, template_code, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"template_code": row.template_code, "configured": row.active}

@router.get("/follow-ups", response_model=list[FollowUpResponse])
def follow_ups(
    status: str | None = None,
    due_before: date | None = None,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("treatment")),
):
    return list_followups(db, status, due_before)


@router.post("/follow-ups", response_model=FollowUpResponse, status_code=201)
def new_follow_up(
    data: FollowUpCreate,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("treatment")),
):
    try:
        return create_followup(db, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/follow-ups/{followup_id}/complete", response_model=FollowUpResponse)
def finish_follow_up(
    followup_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("treatment")),
):
    try:
        return complete_followup(db, followup_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/follow-ups/{followup_id}/cancel", response_model=FollowUpResponse)
def drop_follow_up(
    followup_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("treatment")),
):
    try:
        return cancel_followup(db, followup_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/report")
def treatment_report(
    report_date: date | None = None,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("treatment")),
):
    return report(db, report_date)
