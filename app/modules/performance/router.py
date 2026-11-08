from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.modules.auth.security import require_role

from .schemas import DoctorPerformanceItem
from .service import doctor_performance

router = APIRouter(prefix="/performance", tags=["performance"])


@router.get("/doctors", response_model=list[DoctorPerformanceItem])
def get_doctor_performance(
    doctor_id: int | None = None,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("admin")),
):
    return doctor_performance(db, doctor_id)
