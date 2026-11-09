from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.modules.auth.security import require_role

from .schemas import (
    AcceptanceCreate,
    AcceptanceResponse,
    AdverseCreate,
    AdverseResponse,
    PersonnelCreate,
    PersonnelResponse,
    RecallCreate,
    RecallResponse,
    StorageLogCreate,
    StorageLogResponse,
)
from .service import (
    alerts,
    complete_recall,
    create_acceptance,
    create_adverse,
    create_personnel,
    create_recall,
    create_storage_log,
    list_acceptances,
    list_adverse,
    list_personnel,
    list_recalls,
    list_storage_logs,
)

router = APIRouter(prefix="/gsp", tags=["gsp"])


@router.post("/acceptances", response_model=AcceptanceResponse, status_code=201)
def new_acceptance(
    data: AcceptanceCreate,
    db: Session = Depends(get_db),
    user=Depends(require_role("pharmacist", "warehouse")),
):
    try:
        return create_acceptance(db, data, user.username)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/acceptances", response_model=list[AcceptanceResponse])
def acceptances(
    db: Session = Depends(get_db),
    _: None = Depends(require_role("pharmacist", "warehouse")),
):
    return list_acceptances(db)


@router.post("/storage-logs", response_model=StorageLogResponse, status_code=201)
def new_storage_log(
    data: StorageLogCreate,
    db: Session = Depends(get_db),
    user=Depends(require_role("pharmacist", "warehouse")),
):
    return create_storage_log(db, data, user.username)


@router.get("/storage-logs", response_model=list[StorageLogResponse])
def storage_logs(
    db: Session = Depends(get_db),
    _: None = Depends(require_role("pharmacist", "warehouse")),
):
    return list_storage_logs(db)


@router.post("/adverse-reactions", response_model=AdverseResponse, status_code=201)
def new_adverse(
    data: AdverseCreate,
    db: Session = Depends(get_db),
    user=Depends(require_role("pharmacist", "warehouse")),
):
    return create_adverse(db, data, user.username)


@router.get("/adverse-reactions", response_model=list[AdverseResponse])
def adverse_reactions(
    db: Session = Depends(get_db),
    _: None = Depends(require_role("pharmacist", "warehouse")),
):
    return list_adverse(db)


@router.post("/recalls", response_model=RecallResponse, status_code=201)
def new_recall(
    data: RecallCreate,
    db: Session = Depends(get_db),
    user=Depends(require_role("pharmacist", "warehouse")),
):
    return create_recall(db, data, user.username)


@router.get("/recalls", response_model=list[RecallResponse])
def recalls(
    db: Session = Depends(get_db),
    _: None = Depends(require_role("pharmacist", "warehouse")),
):
    return list_recalls(db)


@router.post("/recalls/{recall_id}/complete", response_model=RecallResponse)
def recall_complete(
    recall_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_role("pharmacist", "warehouse")),
):
    try:
        return complete_recall(db, recall_id, user.username)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/personnel", response_model=PersonnelResponse, status_code=201)
def new_personnel(
    data: PersonnelCreate,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("pharmacist", "warehouse")),
):
    return create_personnel(db, data)


@router.get("/personnel", response_model=list[PersonnelResponse])
def personnel(
    db: Session = Depends(get_db),
    _: None = Depends(require_role("pharmacist", "warehouse")),
):
    return list_personnel(db)


@router.get("/alerts")
def gsp_alerts(
    db: Session = Depends(get_db),
    _: None = Depends(require_role("pharmacist", "warehouse")),
):
    data = alerts(db)
    return {key: len(value) for key, value in data.items()}
