from datetime import date, datetime

from sqlalchemy.orm import Session

from app.modules.drug.service import get_drug
from app.modules.pharmacy.models import DrugStock
from app.modules.stock_ledger.service import record_drug

from .models import NarcoticInventoryCheck, NarcoticLedger


def record_issue(
    db: Session,
    *,
    drug,
    prescription_id,
    dispense_id,
    patient_id,
    batch_no,
    quantity,
    operator,
    witness: str = "",
):
    if not getattr(drug, "controlled_level", ""):
        return
    db.add(
        NarcoticLedger(
            drug_id=drug.id,
            drug_name=drug.name,
            prescription_id=prescription_id,
            dispense_id=dispense_id,
            patient_id=patient_id,
            batch_no=batch_no,
            action="issue",
            quantity=quantity,
            operator=operator,
            witness=witness,
        )
    )


def record_return(db: Session, *, line, dispense_id, quantity, operator):
    issue = (
        db.query(NarcoticLedger)
        .filter(
            NarcoticLedger.dispense_id == dispense_id,
            NarcoticLedger.drug_id == line.drug_id,
            NarcoticLedger.batch_no == line.batch_no,
            NarcoticLedger.action == "issue",
        )
        .order_by(NarcoticLedger.id.desc())
        .first()
    )
    db.add(
        NarcoticLedger(
            drug_id=line.drug_id,
            drug_name=line.drug_name,
            prescription_id=issue.prescription_id if issue else None,
            dispense_id=dispense_id,
            patient_id=issue.patient_id if issue else None,
            batch_no=line.batch_no,
            action="return",
            quantity=quantity,
            operator=operator,
        )
    )


def record_ampoule_return(
    db: Session,
    *,
    drug_id: int | None,
    drug_name: str,
    prescription_id: int | None,
    patient_id: int | None,
    batch_no: str,
    quantity: int,
    operator: str,
    witness: str,
    note: str,
):
    db.add(
        NarcoticLedger(
            drug_id=drug_id,
            drug_name=drug_name,
            prescription_id=prescription_id,
            patient_id=patient_id,
            batch_no=batch_no,
            action="ampoule_return",
            quantity=quantity,
            operator=operator,
            witness=witness,
            note=note,
            created_at=datetime.now(),
        )
    )


def create_inventory_check(db: Session, data, operator: str):
    drug = get_drug(db, data.drug_id)
    if not drug:
        raise ValueError("药品不存在")
    if not getattr(drug, "controlled_level", ""):
        raise ValueError("该药品不是管制药品")
    stock = (
        db.query(DrugStock)
        .filter(DrugStock.drug_id == drug.id, DrugStock.batch_no == data.batch_no)
        .first()
    )
    expected = stock.quantity if stock else 0
    row = NarcoticInventoryCheck(
        drug_id=drug.id,
        drug_name=drug.name,
        batch_no=data.batch_no,
        expected_qty=expected,
        counted_qty=data.counted_qty,
        difference=data.counted_qty - expected,
        reason=data.reason,
        checked_by=operator,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def review_inventory_check(db: Session, check_id: int, approve: bool, note: str, reviewer: str):
    from datetime import date, datetime

    row = db.get(NarcoticInventoryCheck, check_id)
    if not row:
        raise ValueError("盘点单不存在")
    if row.status != "pending":
        raise ValueError("仅待审批盘点单可以审核")
    if not approve and not note.strip():
        raise ValueError("驳回必须填写原因")
    claimed = (
        db.query(NarcoticInventoryCheck)
        .filter(
            NarcoticInventoryCheck.id == check_id,
            NarcoticInventoryCheck.status == "pending",
        )
        .update({NarcoticInventoryCheck.status: "reviewing"}, synchronize_session=False)
    )
    if claimed != 1:
        db.rollback()
        raise ValueError("该盘点单正在审核或已处理")
    row.status = "approved" if approve else "rejected"
    row.approved_by = reviewer
    row.approved_at = datetime.now()
    if approve:
        stock = (
            db.query(DrugStock)
            .filter(DrugStock.drug_id == row.drug_id, DrugStock.batch_no == row.batch_no)
            .first()
        )
        if stock:
            target = stock.quantity + (row.counted_qty - row.expected_qty)
            if target < 0:
                raise ValueError("盘点调整后库存不能为负")
            stock.quantity = target
        elif row.counted_qty > 0:
            raise ValueError("该批次库存不存在，请先核对批号，不能直接建立盘点批次")
        drug = get_drug(db, row.drug_id)
        if drug:
            record_drug(
                db,
                drug,
                batch_no=row.batch_no,
                expiry=stock.expiry if stock else None,
                warehouse="药房",
                direction="in" if row.difference >= 0 else "out",
                quantity=abs(row.difference),
                unit_price=drug.base_price,
                ref_type="narcotic_inventory",
                ref_id=row.id,
                operator=reviewer,
                note=note or "麻精盘点调整",
            )
    db.commit()
    db.refresh(row)
    return row
