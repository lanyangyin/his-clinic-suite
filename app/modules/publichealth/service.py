from datetime import datetime

from sqlalchemy.orm import Session

from app.modules.encounter.service import get_encounter

from .models import DiseaseReport
from .schemas import ReportCreate


def create_report(
    db: Session, data: ReportCreate, reported_by: str = ""
) -> DiseaseReport:
    """创建传染病报告卡（草稿）：同一就诊同一疾病唯一。"""
    if not get_encounter(db, data.encounter_id):
        raise ValueError("就诊记录不存在")

    existing = (
        db.query(DiseaseReport)
        .filter(
            DiseaseReport.encounter_id == data.encounter_id,
            DiseaseReport.disease_code == data.disease_code,
        )
        .first()
    )
    if existing:
        raise ValueError("该就诊该疾病已创建报告卡")

    report = DiseaseReport(
        encounter_id=data.encounter_id,
        disease_code=data.disease_code,
        disease_name=data.disease_name,
        status="draft",
        reported_by=reported_by,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


def get_report(db: Session, report_id: int) -> DiseaseReport | None:
    return db.get(DiseaseReport, report_id)


def list_reports(db: Session, status: str | None = None) -> list[DiseaseReport]:
    query = db.query(DiseaseReport)
    if status is not None:
        query = query.filter(DiseaseReport.status == status)
    return query.order_by(DiseaseReport.id.desc()).all()


def submit_report(db: Session, report_id: int) -> DiseaseReport:
    """上报区域平台（模拟）：草稿 → 已上报，记录上报时间。"""
    report = get_report(db, report_id)
    if not report:
        raise ValueError("报告卡不存在")
    if report.status != "draft":
        raise ValueError("该报告卡已上报")

    report.status = "submitted"
    report.submitted_at = datetime.now()
    db.commit()
    db.refresh(report)
    return report
