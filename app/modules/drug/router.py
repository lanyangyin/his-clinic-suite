from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.modules.auth.security import require_role

from .schemas import DrugCreate, DrugResponse
from .service import create_drug, get_drug, list_drugs

router = APIRouter(prefix="/drugs", tags=["drugs"])


@router.post("/", response_model=DrugResponse, status_code=201)
def new_drug(
    data: DrugCreate,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("admin")),
):
    return create_drug(db, data)


@router.get("/", response_model=list[DrugResponse])
def get_all(name: str | None = None, db: Session = Depends(get_db)):
    return list_drugs(db, name)


@router.get("/{drug_id}", response_model=DrugResponse)
def get_drug_one(drug_id: int, db: Session = Depends(get_db)):
    drug = get_drug(db, drug_id)
    if not drug:
        raise HTTPException(status_code=404, detail="药品不存在")
    return drug
