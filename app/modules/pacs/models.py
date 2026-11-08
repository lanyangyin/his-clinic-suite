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
    # pending 已申请 / reported 已出报告
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    requested_by: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    requested_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, nullable=False
    )
    reported_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    report: Mapped[str | None] = mapped_column(String(500), nullable=True)
    image_url: Mapped[str] = mapped_column(String(200), default="", nullable=False)

    item = relationship("ImagingItem")

    @property
    def item_name(self) -> str:
        return self.item.name if self.item else ""
