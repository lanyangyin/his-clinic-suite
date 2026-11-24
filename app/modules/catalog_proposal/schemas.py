from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class CatalogProposalCreate(BaseModel):
    kind: Literal["drug", "treatment"]
    name: str = Field(min_length=1, max_length=100)
    spec: str = Field(default="", max_length=50)
    unit: str = Field(default="", max_length=20)
    price: float = Field(default=0, ge=0)
    reason: str = Field(default="", max_length=500)


class CatalogProposalReview(BaseModel):
    approve: bool
    note: str = Field(default="", max_length=300)


class CatalogProposalResponse(BaseModel):
    id: int
    kind: str
    name: str
    spec: str
    unit: str
    price: float
    reason: str
    status: str
    requested_by: str
    reviewed_by: str
    review_note: str
    created_object_id: int | None
    created_at: datetime
    reviewed_at: datetime | None
    model_config = ConfigDict(from_attributes=True)
