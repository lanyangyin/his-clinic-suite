from datetime import date

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.modules.auth.security import require_role

from .schemas import DepartmentRevenueItem
from .service import department_revenue
from app.modules.bi.export import department_workbook

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

@router.get("/departments/revenue/export.xlsx")
def export_department_revenue(
    start_date: date | None = None,
    end_date: date | None = None,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("admin")),
):
    rows = department_revenue(db, start_date, end_date)
    stream = department_workbook(rows)
    label = f"{start_date or 'all'}_{end_date or 'all'}"
    return StreamingResponse(
        stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="department_revenue_{label}.xlsx"'},
    )
