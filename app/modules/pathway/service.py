from datetime import datetime

from sqlalchemy.orm import Session

from app.modules.inpatient.service import get_admission

from .models import ClinicalPathway, PathwayEnrollment, PathwayVariance
from .schemas import PathwayCreate, VarianceCreate


def create_pathway(db: Session, data: PathwayCreate) -> ClinicalPathway:
    """维护临床路径模板：名称唯一。"""
    existing = db.query(ClinicalPathway).filter(ClinicalPathway.name == data.name).first()
    if existing:
        raise ValueError("临床路径名称已存在")

    pathway = ClinicalPathway(**data.model_dump())
    db.add(pathway)
    db.commit()
    db.refresh(pathway)
    return pathway


def get_pathway(db: Session, pathway_id: int) -> ClinicalPathway | None:
    return db.get(ClinicalPathway, pathway_id)


def list_pathways(db: Session, diagnosis: str | None = None) -> list[ClinicalPathway]:
    query = db.query(ClinicalPathway)
    if diagnosis is not None:
        query = query.filter(ClinicalPathway.diagnosis == diagnosis)
    return query.order_by(ClinicalPathway.id).all()


def enroll(db: Session, pathway_id: int, admission_id: int) -> PathwayEnrollment:
    """入径：路径存在、患者在院、不能重复入同一路径。"""
    if not get_pathway(db, pathway_id):
        raise ValueError("临床路径不存在")
    admission = get_admission(db, admission_id)
    if not admission:
        raise ValueError("住院记录不存在")
    if admission.status != "in":
        raise ValueError("该患者已出院，不能入径")

    existing = (
        db.query(PathwayEnrollment)
        .filter(
            PathwayEnrollment.pathway_id == pathway_id,
            PathwayEnrollment.admission_id == admission_id,
        )
        .first()
    )
    if existing:
        raise ValueError("该患者已在该路径中")

    enrollment = PathwayEnrollment(
        pathway_id=pathway_id, admission_id=admission_id, status="active"
    )
    db.add(enrollment)
    db.commit()
    db.refresh(enrollment)
    return enrollment


def get_enrollment(db: Session, enrollment_id: int) -> PathwayEnrollment | None:
    return db.get(PathwayEnrollment, enrollment_id)


def list_enrollments(db: Session, admission_id: int) -> list[PathwayEnrollment]:
    return (
        db.query(PathwayEnrollment)
        .filter(PathwayEnrollment.admission_id == admission_id)
        .order_by(PathwayEnrollment.id)
        .all()
    )


def add_variance(
    db: Session, enrollment_id: int, data: VarianceCreate, noted_by: str = ""
) -> PathwayVariance:
    """记录路径变异：仅进行中的路径可记录。"""
    enrollment = get_enrollment(db, enrollment_id)
    if not enrollment:
        raise ValueError("入径记录不存在")
    if enrollment.status != "active":
        raise ValueError("仅进行中的路径可记录变异")

    variance = PathwayVariance(
        enrollment_id=enrollment_id, reason=data.reason, noted_by=noted_by
    )
    db.add(variance)
    db.commit()
    db.refresh(variance)
    return variance


def list_variances(db: Session, enrollment_id: int) -> list[PathwayVariance]:
    return (
        db.query(PathwayVariance)
        .filter(PathwayVariance.enrollment_id == enrollment_id)
        .order_by(PathwayVariance.id)
        .all()
    )


def complete(db: Session, enrollment_id: int) -> PathwayEnrollment:
    """完成路径：仅进行中的路径可以完成。"""
    enrollment = get_enrollment(db, enrollment_id)
    if not enrollment:
        raise ValueError("入径记录不存在")
    if enrollment.status != "active":
        raise ValueError("仅进行中的路径可以完成")

    enrollment.status = "completed"
    enrollment.completed_at = datetime.now()
    db.commit()
    db.refresh(enrollment)
    return enrollment


def withdraw(db: Session, enrollment_id: int) -> PathwayEnrollment:
    """退出路径：仅进行中的路径可以退出。"""
    enrollment = get_enrollment(db, enrollment_id)
    if not enrollment:
        raise ValueError("入径记录不存在")
    if enrollment.status != "active":
        raise ValueError("仅进行中的路径可以退出")

    enrollment.status = "withdrawn"
    db.commit()
    db.refresh(enrollment)
    return enrollment
