from sqlalchemy.orm import Session

from .models import Drug
from .schemas import DrugCreate


def create_drug(db: Session, data: DrugCreate) -> Drug:
    """创建药品：同名药品返回已有记录。"""
    existing = db.query(Drug).filter(Drug.name == data.name).first()
    if existing:
        return existing

    drug = Drug(**data.model_dump())
    db.add(drug)
    db.commit()
    db.refresh(drug)
    return drug


def get_drug(db: Session, drug_id: int) -> Drug | None:
    """按 ID 查询药品；不存在时返回 None。"""
    return db.get(Drug, drug_id)


def list_drugs(db: Session, name: str | None = None) -> list[Drug]:
    """药品列表（可按名称过滤）。"""
    query = db.query(Drug)
    if name is not None:
        query = query.filter(Drug.name == name)
    return query.order_by(Drug.id).all()
