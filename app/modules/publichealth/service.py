from datetime import datetime

from sqlalchemy.orm import Session

from app.modules.encounter.service import get_encounter

from .models import DiseaseReport
from .schemas import ReportCreate


class PublicHealthUnavailable(RuntimeError):
    """区域公卫平台未配置或不可用。"""


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
        report_type=data.report_type,
        onset_date=data.onset_date,
        diagnosis_date=data.diagnosis_date,
        report_unit=data.report_unit,
        reporter_phone=data.reporter_phone,
        is_correction=data.is_correction,
        correction_reason=data.correction_reason,
        is_death=data.is_death,
        death_date=data.death_date,
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

    from app import settings

    gateway_url = (getattr(settings, "PUBLIC_HEALTH_GATEWAY_URL", "") or "").strip()
    if gateway_url:
        import json
        import urllib.request

        payload = json.dumps(
            {
                "encounter_id": report.encounter_id,
                "disease_code": report.disease_code,
                "disease_name": report.disease_name,
                "report_type": report.report_type,
                "onset_date": report.onset_date.isoformat() if report.onset_date else None,
                "diagnosis_date": report.diagnosis_date.isoformat() if report.diagnosis_date else None,
                "report_unit": report.report_unit,
                "reporter_phone": report.reporter_phone,
                "is_death": report.is_death,
                "death_date": report.death_date.isoformat() if report.death_date else None,
            },
            ensure_ascii=False,
        ).encode("utf-8")
        request = urllib.request.Request(
            gateway_url,
            data=payload,
            headers={
                "Content-Type": "application/json; charset=utf-8",
                "Authorization": f"Bearer {getattr(settings, 'PUBLIC_HEALTH_GATEWAY_TOKEN', '')}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=8) as response:
                if not 200 <= response.status < 300:
                    raise PublicHealthUnavailable(f"公卫平台返回 {response.status}")
                body = json.loads(response.read().decode("utf-8"))
        except PublicHealthUnavailable:
            raise
        except Exception as e:
            report.submit_error = f"区域公卫平台调用失败：{e}"[:300]
            db.commit()
            raise PublicHealthUnavailable("区域公卫平台调用失败") from e
        receipt = str(body.get("receipt_no") or body.get("receiptNo") or "").strip()
        if not receipt:
            raise PublicHealthUnavailable("公卫平台响应缺少回执号")
        report.status = "submitted"
        report.submitted_at = datetime.now()
        report.receipt_no = receipt[:60]
        report.submit_error = ""
        db.commit()
        return report

    if not getattr(settings, "PUBLIC_HEALTH_ALLOW_MOCK", False):
        report.submit_error = "区域公卫平台未配置"
        db.commit()
        raise PublicHealthUnavailable("区域公卫平台未配置")

    report.status = "submitted"
    report.submitted_at = datetime.now()
    report.receipt_no = f"MOCK-PH-{report.id:08d}"
    report.submit_error = ""
    db.commit()
    db.refresh(report)
    return report
