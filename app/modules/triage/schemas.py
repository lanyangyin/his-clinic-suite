from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TicketCreate(BaseModel):
    registration_id: int


class TicketResponse(TicketCreate):
    id: int
    status: str
    created_at: datetime
    called_at: datetime | None
    passed_at: datetime | None
    done_at: datetime | None
    model_config = ConfigDict(from_attributes=True)
