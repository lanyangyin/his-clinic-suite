from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.modules.auth.security import require_role

from .schemas import DrugCreate, DrugInteractionCreate, DrugInteractionResponse, DrugResponse
from .models import DrugInteraction
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


@router.get("/interactions", response_model=list[DrugInteractionResponse])
def list_interactions(db: Session = Depends(get_db)):
    return db.query(DrugInteraction).order_by(DrugInteraction.id.desc()).all()


@router.post("/interactions", response_model=DrugInteractionResponse, status_code=201)
def create_interaction(
    data: DrugInteractionCreate,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("admin")),
):
    if data.drug_a_id == data.drug_b_id:
        raise HTTPException(status_code=400, detail="不能配置同一药品的相互作用")
    if not get_drug(db, data.drug_a_id) or not get_drug(db, data.drug_b_id):
        raise HTTPException(status_code=404, detail="药品不存在")
    existing = (
        db.query(DrugInteraction)
        .filter(
            ((DrugInteraction.drug_a_id == data.drug_a_id) & (DrugInteraction.drug_b_id == data.drug_b_id))
            | ((DrugInteraction.drug_a_id == data.drug_b_id) & (DrugInteraction.drug_b_id == data.drug_a_id))
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="该药品对已配置")
    row = DrugInteraction(**data.model_dump(), active=True)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.get("/by-barcode/{barcode}", response_model=DrugResponse)
def get_by_barcode(barcode: str, db: Session = Depends(get_db)):
    from .models import Drug

    drug = db.query(Drug).filter(Drug.barcode == barcode.strip()).first()
    if not drug:
        raise HTTPException(status_code=404, detail="条码对应药品不存在")
    return drug


@router.get("/{drug_id}", response_model=DrugResponse)
def get_drug_one(drug_id: int, db: Session = Depends(get_db)):
    drug = get_drug(db, drug_id)
    if not drug:
        raise HTTPException(status_code=404, detail="药品不存在")
    return drug
