from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class CatalogProposal(Base):
    """医生提交的新药品/新治疗项目建议，审批通过后才写入主数据。"""

    __tablename__ = "catalog_proposals"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    kind: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    spec: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    unit: Mapped[str] = mapped_column(String(20), default="", nullable=False)
    price: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    reason: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="pending", nullable=False, index=True)
    requested_by: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    reviewed_by: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    review_note: Mapped[str] = mapped_column(String(300), default="", nullable=False)
    created_object_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
