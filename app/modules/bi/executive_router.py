from datetime import date

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.modules.auth.security import require_role

from .executive import executive
from .export import executive_workbook

router = APIRouter(prefix="/bi", tags=["bi"])


@router.get("/executive")
def get_executive(
    start_date: date | None = None,
    end_date: date | None = None,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("admin")),
):
    return executive(db, start_date, end_date)

@router.get("/executive/export.xlsx")
def export_executive(
    start_date: date | None = None,
    end_date: date | None = None,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("admin")),
):
    data = executive(db, start_date, end_date)
    stream = executive_workbook(data)
    filename = f"executive_{data['start_date']}_{data['end_date']}.xlsx"
    return StreamingResponse(
        stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
