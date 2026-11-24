import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class ImagingItem(Base):
    __tablename__ = "imaging_items"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    body_part: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    price: Mapped[float] = mapped_column(default=0.0, server_default="0", nullable=False)
    insurance_ratio: Mapped[float] = mapped_column(default=0.7, server_default="0.7", nullable=False)


class ImagingReportTemplate(Base):
    """影像报告模板：按检查部位/项目预置所见与意见。"""

    __tablename__ = "imaging_report_templates"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    body_part: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    findings: Mapped[str] = mapped_column(String(1000), default="", nullable=False)
    impression: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    active: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)


class ImagingRequest(Base):
    __tablename__ = "imaging_requests"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    encounter_id: Mapped[int] = mapped_column(
        ForeignKey("encounters.id"), nullable=False, index=True
    )
    item_id: Mapped[int] = mapped_column(ForeignKey("imaging_items.id"), nullable=False)
    # 影像号：RIS 申请与 PACS 检查的关联标识
    accession_no: Mapped[str] = mapped_column(
        String(30), unique=True, default=lambda: f"ACC{uuid.uuid4().hex[:10].upper()}",
        nullable=False,
    )
    # pending 已申请 / reported 已出报告 / reviewed 已审核 / rejected 已退回
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    # routine 普通 / urgent 加急
    priority: Mapped[str] = mapped_column(
        String(10), default="routine", server_default="routine", nullable=False
    )
    requested_by: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    requested_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, nullable=False
    )
    reported_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reported_by: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    reviewed_by: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    review_note: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    report: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    findings: Mapped[str] = mapped_column(String(1000), default="", nullable=False)
    impression: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    template_name: Mapped[str] = mapped_column(String(100), default="", nullable=False)
    image_url: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    study_uid: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    series_uid: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    modality: Mapped[str] = mapped_column(String(20), default="", nullable=False)

    item = relationship("ImagingItem")

    @property
    def item_name(self) -> str:
        return self.item.name if self.item else ""
