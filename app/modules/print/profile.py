"""机构级打印外观：读取/保存单例配置，缺省回退到 config.ini。"""
from datetime import datetime

from sqlalchemy.orm import Session

from app import settings
from app.modules.admin.models import InstitutionSetting
from .models import PrintProfile

FIELDS = (
    "clinic_name", "clinic_address", "clinic_phone", "logo_url",
    "theme_color", "font_family", "paper_size", "margin_mm",
    "header_note", "footer_note", "doctor_label",
    "reviewer_label", "dispenser_label", "checker_label", "custom_css",
)


def _row(db: Session) -> PrintProfile:
    row = db.get(PrintProfile, 1)
    if row is None:
        row = PrintProfile(id=1)
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


def load(db: Session) -> dict:
    row = _row(db)
    institution = db.get(InstitutionSetting, 1)
    return {
        "clinic_name": row.clinic_name or (institution.clinic_name if institution else "") or settings.CLINIC_NAME,
        "clinic_address": row.clinic_address or (institution.clinic_address if institution else "") or settings.CLINIC_ADDRESS,
        "clinic_phone": row.clinic_phone or (institution.clinic_phone if institution else "") or settings.CLINIC_PHONE,
        "logo_url": row.logo_url,
        "theme_color": row.theme_color or "#111111",
        "font_family": row.font_family or '"Microsoft YaHei", "SimSun", sans-serif',
        "paper_size": row.paper_size if row.paper_size in ("A4", "A5") else "A4",
        "margin_mm": row.margin_mm if 5 <= row.margin_mm <= 40 else 12,
        "header_note": row.header_note,
        "footer_note": row.footer_note,
        "doctor_label": row.doctor_label or "医师",
        "reviewer_label": row.reviewer_label or "审核药师",
        "dispenser_label": row.dispenser_label or "调配药师",
        "checker_label": row.checker_label or "核对、发药药师",
        "custom_css": row.custom_css,
    }


def save(db: Session, values: dict, operator: str = "") -> dict:
    row = _row(db)
    for field in FIELDS:
        if field in values:
            setattr(row, field, values[field])
    row.margin_mm = max(5, min(40, int(row.margin_mm or 12)))
    if row.paper_size not in ("A4", "A5"):
        row.paper_size = "A4"
    row.updated_by = operator
    row.updated_at = datetime.now()
    db.commit()
    db.refresh(row)
    return load(db)
