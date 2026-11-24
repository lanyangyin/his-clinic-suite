from datetime import datetime

from sqlalchemy.orm import Session

from .models import CatalogProposal


DRUG_PHARMACY = "pending_pharmacy"
DRUG_WAREHOUSE = "pending_warehouse"
TREATMENT_DIRECTOR = "pending_director"
APPROVED = "approved"
REJECTED = "rejected"


def create_proposal(db: Session, data, requested_by: str) -> CatalogProposal:
    status = DRUG_PHARMACY if data.kind == "drug" else TREATMENT_DIRECTOR
    row = CatalogProposal(
        kind=data.kind,
        name=data.name.strip(),
        spec=data.spec.strip(),
        unit=data.unit.strip(),
        price=float(data.price or 0),
        reason=data.reason.strip(),
        status=status,
        requested_by=requested_by,
    )
    db.add(row)
    db.flush()
    from app.modules.approval.service import ensure_request

    ensure_request(
        db,
        "catalog_proposal",
        row.id,
        f"{'药品' if data.kind == 'drug' else '治疗项目'}建议：{row.name}",
        "pharmacist" if data.kind == "drug" else "director",
        applicant=requested_by,
        steps_override=(
            [("pharmacist", 24), ("warehouse", 24)]
            if data.kind == "drug"
            else [("director", 24)]
        ),
    )
    db.commit()
    db.refresh(row)
    return row


def list_proposals(
    db: Session,
    role: str,
    status: str | None = None,
    mine: str | None = None,
) -> list[CatalogProposal]:
    query = db.query(CatalogProposal)
    if mine:
        query = query.filter(CatalogProposal.requested_by == mine)
    elif role == "pharmacist":
        query = query.filter(
            CatalogProposal.kind == "drug",
            CatalogProposal.status == DRUG_PHARMACY,
        )
    elif role == "warehouse":
        query = query.filter(
            CatalogProposal.kind == "drug",
            CatalogProposal.status == DRUG_WAREHOUSE,
        )
    elif role == "director":
        query = query.filter(
            CatalogProposal.kind == "treatment",
            CatalogProposal.status == TREATMENT_DIRECTOR,
        )
    if status:
        query = query.filter(CatalogProposal.status == status)
    return query.order_by(CatalogProposal.id.desc()).all()


def review_proposal(
    db: Session,
    proposal_id: int,
    role: str,
    approve: bool,
    note: str,
    reviewer: str,
) -> CatalogProposal:
    row = db.get(CatalogProposal, proposal_id)
    if not row:
        raise ValueError("建议不存在")
    if row.status in (APPROVED, REJECTED):
        raise ValueError("该建议已处理")

    allowed = (
        (row.kind == "drug" and role == "pharmacist" and row.status == DRUG_PHARMACY)
        or (row.kind == "drug" and role == "warehouse" and row.status == DRUG_WAREHOUSE)
        or (row.kind == "treatment" and role == "director" and row.status == TREATMENT_DIRECTOR)
        or role == "admin"
    )
    if not allowed:
        raise ValueError("当前角色/阶段不能审核该建议")

    from app.modules.approval.service import advance_request

    result = advance_request(
        db,
        "catalog_proposal",
        row.id,
        "approve" if approve else "reject",
        reviewer,
        note,
    )
    row.reviewed_by = reviewer
    row.review_note = note.strip()
    row.reviewed_at = datetime.now()

    if result == "rejected" or not approve:
        row.status = REJECTED
        db.commit()
        db.refresh(row)
        return row

    if result == "pending":
        row.status = DRUG_WAREHOUSE if row.kind == "drug" else TREATMENT_DIRECTOR
        db.commit()
        db.refresh(row)
        return row

    # 最终通过：写主数据
    if row.kind == "drug":
        from app.modules.drug.models import Drug

        if db.query(Drug).filter(Drug.name == row.name).first():
            raise ValueError("药品名称已存在，不能重复建立")
        drug = Drug(
            name=row.name,
            spec=row.spec,
            unit=row.unit or "盒",
            base_price=row.price,
            dosage_form="",
            ingredient="",
            barcode="",
            insurance_code="",
            approval_no="",
            manufacturer="",
        )
        db.add(drug)
        db.flush()
        row.status = APPROVED
        row.created_object_id = drug.id
    else:
        from app.modules.charges.models import ChargeItem

        code = f"PROP{row.id:06d}"
        if db.query(ChargeItem).filter(ChargeItem.code == code).first():
            raise ValueError("治疗项目编码已存在")
        item = ChargeItem(
            code=code,
            name=row.name,
            category="treatment",
            price=row.price,
            unit=row.unit or "次",
            active=True,
        )
        db.add(item)
        db.flush()
        row.status = APPROVED
        row.created_object_id = item.id
    db.commit()
    db.refresh(row)
    return row
