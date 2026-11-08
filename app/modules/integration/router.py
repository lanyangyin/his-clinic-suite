from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.modules.auth.security import require_role
from app.modules.patient.service import get_patient

from .schemas import Hl7Message, Hl7Result, IntegrationLogResponse
from .service import handle_hl7_adt, list_logs, to_fhir_patient

router = APIRouter(prefix="/integration", tags=["integration"])


@router.get("/fhir/Patient/{patient_id}")
def fhir_patient(patient_id: int, db: Session = Depends(get_db)):
    """FHIR R4 Patient 资源查询。"""
    patient = get_patient(db, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="患者不存在")
    return to_fhir_patient(patient)


@router.post("/hl7/adt", response_model=Hl7Result, status_code=201)
def hl7_adt(data: Hl7Message, db: Session = Depends(get_db)):
    """接收 HL7 v2 ADT 消息（PID 段建档，身份证号幂等）。"""
    try:
        return handle_hl7_adt(db, data.message)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/logs", response_model=list[IntegrationLogResponse])
def get_logs(
    limit: int = 50,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("admin")),
):
    return list_logs(db, max(1, min(limit, 200)))
