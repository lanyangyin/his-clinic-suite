from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.modules.auth.security import require_read_login, require_role

from .service import list_values, set_values

router = APIRouter(prefix="/integrations", tags=["integrations"], dependencies=[Depends(require_read_login)])


class IntegrationUpdate(BaseModel):
    values: dict[str, str]


@router.get("")
def get_integrations(
    db: Session = Depends(get_db),
    _: None = Depends(require_role("admin")),
):
    return list_values(db)


@router.put("")
def put_integrations(
    data: IntegrationUpdate,
    db: Session = Depends(get_db),
    user=Depends(require_role("admin")),
):
    set_values(db, data.values, user.username)
    return list_values(db)
