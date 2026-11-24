from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.modules.auth.security import require_read_login, require_role
from app.modules.drug.service import get_drug

from .models import NarcoticLedger
from .models import NarcoticInventoryCheck
from .schemas import AmpouleReturnRequest, InventoryCheckCreate, InventoryCheckReview
from .service import create_inventory_check, record_ampoule_return, review_inventory_check

router = APIRouter(prefix="/narcotic", tags=["narcotic"], dependencies=[Depends(require_read_login)])


@router.get("/ledger")
def ledger(
    action: str | None = None,
    drug_id: int | None = None,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("admin", "director", "pharmacist")),
):
    query = db.query(NarcoticLedger)
    if action:
        query = query.filter(NarcoticLedger.action == action)
    if drug_id:
        query = query.filter(NarcoticLedger.drug_id == drug_id)
    rows = query.order_by(NarcoticLedger.id.desc()).limit(500).all()
    return [
        {
            "id": row.id,
            "drug_id": row.drug_id,
            "drug_name": row.drug_name,
            "prescription_id": row.prescription_id,
            "dispense_id": row.dispense_id,
            "patient_id": row.patient_id,
            "batch_no": row.batch_no,
            "action": row.action,
            "quantity": row.quantity,
            "operator": row.operator,
            "witness": row.witness,
            "note": row.note,
            "created_at": row.created_at,
        }
        for row in rows
    ]


@router.post("/ampoule-return")
def ampoule_return(
    data: AmpouleReturnRequest,
    db: Session = Depends(get_db),
    user=Depends(require_role("nurse", "pharmacist")),
):
    drug = get_drug(db, data.drug_id)
    if not drug:
        raise HTTPException(status_code=404, detail="药品不存在")
    if not getattr(drug, "controlled_level", ""):
        raise HTTPException(status_code=400, detail="该药品不是管制药品")
    record_ampoule_return(
        db,
        drug_id=drug.id,
        drug_name=drug.name,
        prescription_id=data.prescription_id,
        patient_id=data.patient_id,
        batch_no=data.batch_no,
        quantity=data.quantity,
        operator=user.username,
        witness=data.witness,
        note=data.note,
    )
    db.commit()
    return {"ok": True}


@router.get("/inventory-checks")
def inventory_checks(
    db: Session = Depends(get_db),
    _: None = Depends(require_role("admin", "director", "pharmacist")),
):
    rows = (
        db.query(NarcoticInventoryCheck)
        .order_by(NarcoticInventoryCheck.id.desc())
        .limit(200)
        .all()
    )
    return [
        {
            "id": row.id,
            "drug_id": row.drug_id,
            "drug_name": row.drug_name,
            "batch_no": row.batch_no,
            "expected_qty": row.expected_qty,
            "counted_qty": row.counted_qty,
            "difference": row.difference,
            "reason": row.reason,
            "status": row.status,
            "checked_by": row.checked_by,
            "approved_by": row.approved_by,
            "approved_at": row.approved_at,
            "created_at": row.created_at,
        }
        for row in rows
    ]


@router.post("/inventory-checks", status_code=201)
def create_inventory(
    data: InventoryCheckCreate,
    db: Session = Depends(get_db),
    user=Depends(require_role("pharmacist")),
):
    try:
        row = create_inventory_check(db, data, user.username)
        return {"id": row.id, "difference": row.difference, "status": row.status}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/inventory-checks/{check_id}/review")
def review_inventory(
    check_id: int,
    data: InventoryCheckReview,
    db: Session = Depends(get_db),
    user=Depends(require_role("admin", "director")),
):
    try:
        row = review_inventory_check(
            db, check_id, data.approve, data.note, user.username
        )
        return {"id": row.id, "status": row.status, "difference": row.difference}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
