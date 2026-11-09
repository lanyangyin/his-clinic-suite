from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.modules.auth.security import require_role

from .executive import executive

router = APIRouter(prefix="/bi", tags=["bi"])


@router.get("/executive")
def get_executive(
    start_date: date | None = None,
    end_date: date | None = None,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("admin")),
):
    return executive(db, start_date, end_date)
