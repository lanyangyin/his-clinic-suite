from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.modules.auth.security import require_role

from .schemas import StockMovementResponse
from .service import list_movements

router = APIRouter(prefix="/stock", tags=["stock-ledger"])


@router.get("/ledger", response_model=list[StockMovementResponse])
def get_ledger(
    kind: str | None = None,
    drug_id: int | None = None,
    material_id: int | None = None,
    warehouse: str | None = None,
    direction: str | None = None,
    ref_type: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    limit: int = 200,
    offset: int = 0,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("warehouse", "pharmacist")),
):
    """库存流水查询（库房/药房可看；admin 恒允许）。"""
    return list_movements(
        db,
        kind,
        drug_id,
        material_id,
        warehouse,
        direction,
        ref_type,
        start_date,
        end_date,
        limit,
        offset,
    )
