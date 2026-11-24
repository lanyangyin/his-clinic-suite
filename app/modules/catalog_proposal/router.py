from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.modules.auth.security import require_read_login, require_role

from .schemas import CatalogProposalCreate, CatalogProposalResponse, CatalogProposalReview
from .service import create_proposal, list_proposals, review_proposal

from app.modules.approval.service import record_event

router = APIRouter(prefix="/catalog-proposals", tags=["catalog-proposals"], dependencies=[Depends(require_read_login)])


@router.post("/", response_model=CatalogProposalResponse, status_code=201)
def submit(
    data: CatalogProposalCreate,
    db: Session = Depends(get_db),
    user=Depends(require_role("doctor")),
):
    row = create_proposal(db, data, user.username)
    record_event(db, "catalog_proposal", row.id, "submit", user.username, data.reason)
    return row


@router.get("/mine", response_model=list[CatalogProposalResponse])
def mine(
    db: Session = Depends(get_db),
    user=Depends(require_role("doctor")),
):
    return list_proposals(db, "doctor", mine=user.username)


@router.get("/", response_model=list[CatalogProposalResponse])
def pending(
    db: Session = Depends(get_db),
    user=Depends(require_role("pharmacist", "warehouse", "director")),
):
    return list_proposals(db, user.role)


@router.post("/{proposal_id}/review", response_model=CatalogProposalResponse)
def review(
    proposal_id: int,
    data: CatalogProposalReview,
    db: Session = Depends(get_db),
    user=Depends(require_role("pharmacist", "warehouse", "director")),
):
    try:
        row = review_proposal(
            db,
            proposal_id,
            user.role,
            data.approve,
            data.note,
            user.username,
        )
        record_event(
            db,
            "catalog_proposal",
            row.id,
            "approve" if data.approve else "reject",
            user.username,
            data.note,
            step=user.role,
        )
        return row
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
