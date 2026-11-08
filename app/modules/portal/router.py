from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db

from .schemas import PortalPatientResponse, PortalReportsResponse
from .service import get_portal_patient, get_portal_reports

router = APIRouter(prefix="/portal", tags=["portal"])


@router.get("/patients/{id_number}", response_model=PortalPatientResponse)
def patient_portal(id_number: str, db: Session = Depends(get_db)):
    """患者自助查询（演示：身份证号作为身份凭据）。"""
    try:
        return get_portal_patient(db, id_number)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/reports/{id_number}", response_model=PortalReportsResponse)
def patient_reports(id_number: str, db: Session = Depends(get_db)):
    """患者自助查询已出结果的检验/检查报告。"""
    try:
        return get_portal_reports(db, id_number)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
