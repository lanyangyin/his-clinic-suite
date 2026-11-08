from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class StockMovementResponse(BaseModel):
    id: int
    kind: str
    drug_id: int | None
    material_id: int | None
    name: str
    spec: str
    unit: str
    batch_no: str
    expiry: date | None
    warehouse: str
    direction: str
    quantity: int
    unit_price: float
    amount: float
    balance_after: int
    ref_type: str
    ref_id: int | None
    operator: str
    note: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
