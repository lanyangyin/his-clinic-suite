from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.modules.auth.security import require_role

from .schemas import DepartmentRevenueItem
from .service import department_revenue

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/departments/revenue", response_model=list[DepartmentRevenueItem])
def get_department_revenue(
    start_date: date | None = None,
    end_date: date | None = None,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("admin")),
):
    """科室收入报表（按费用明细汇总，支持日期范围）。"""
    return department_revenue(db, start_date, end_date)
