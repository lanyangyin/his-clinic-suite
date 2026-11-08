from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.modules.auth.security import require_role

from .schemas import (
    EnrollmentResponse,
    EnrollRequest,
    PathwayCreate,
    PathwayResponse,
    VarianceCreate,
    VarianceResponse,
)
from .service import (
    add_variance,
    complete,
    create_pathway,
    enroll,
    get_enrollment,
    get_pathway,
    list_enrollments,
    list_pathways,
    list_variances,
    withdraw,
)

router = APIRouter(prefix="/pathways", tags=["pathway"])

_NOT_FOUND = {"临床路径不存在", "住院记录不存在", "入径记录不存在"}


def _code(message: str) -> int:
    return 404 if message in _NOT_FOUND else 400


@router.post("/", response_model=PathwayResponse, status_code=201)
def new_pathway(
    data: PathwayCreate,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("admin")),
):
    try:
        return create_pathway(db, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/", response_model=list[PathwayResponse])
def get_all(diagnosis: str | None = None, db: Session = Depends(get_db)):
    return list_pathways(db, diagnosis)


@router.get("/{pathway_id}", response_model=PathwayResponse)
def get_one(pathway_id: int, db: Session = Depends(get_db)):
    pathway = get_pathway(db, pathway_id)
    if not pathway:
        raise HTTPException(status_code=404, detail="临床路径不存在")
    return pathway


@router.post("/{pathway_id}/enroll", response_model=EnrollmentResponse, status_code=201)
def enroll_patient(
    pathway_id: int,
    data: EnrollRequest,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("doctor")),
):
    try:
        return enroll(db, pathway_id, data.admission_id)
    except ValueError as e:
        raise HTTPException(status_code=_code(str(e)), detail=str(e))


@router.get(
    "/enrollments/admission/{admission_id}", response_model=list[EnrollmentResponse]
)
def get_admission_enrollments(admission_id: int, db: Session = Depends(get_db)):
    return list_enrollments(db, admission_id)


@router.get("/enrollments/{enrollment_id}", response_model=EnrollmentResponse)
def get_enrollment_one(enrollment_id: int, db: Session = Depends(get_db)):
    enrollment = get_enrollment(db, enrollment_id)
    if not enrollment:
        raise HTTPException(status_code=404, detail="入径记录不存在")
    return enrollment


@router.post("/enrollments/{enrollment_id}/variance", response_model=VarianceResponse)
def new_variance(
    enrollment_id: int,
    data: VarianceCreate,
    db: Session = Depends(get_db),
    user=Depends(require_role("nurse")),
):
    try:
        return add_variance(db, enrollment_id, data, user.username)
    except ValueError as e:
        raise HTTPException(status_code=_code(str(e)), detail=str(e))


@router.get("/enrollments/{enrollment_id}/variances", response_model=list[VarianceResponse])
def get_variances(enrollment_id: int, db: Session = Depends(get_db)):
    enrollment = get_enrollment(db, enrollment_id)
    if not enrollment:
        raise HTTPException(status_code=404, detail="入径记录不存在")
    return list_variances(db, enrollment_id)


@router.post("/enrollments/{enrollment_id}/complete", response_model=EnrollmentResponse)
def complete_enrollment(
    enrollment_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("doctor")),
):
    try:
        return complete(db, enrollment_id)
    except ValueError as e:
        raise HTTPException(status_code=_code(str(e)), detail=str(e))


@router.post("/enrollments/{enrollment_id}/withdraw", response_model=EnrollmentResponse)
def withdraw_enrollment(
    enrollment_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("doctor")),
):
    try:
        return withdraw(db, enrollment_id)
    except ValueError as e:
        raise HTTPException(status_code=_code(str(e)), detail=str(e))
