from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class LabItem(Base):
    __tablename__ = "lab_items"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    price: Mapped[float] = mapped_column(default=0.0, server_default="0", nullable=False)


class LabRequest(Base):
    __tablename__ = "lab_requests"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    encounter_id: Mapped[int] = mapped_column(
        ForeignKey("encounters.id"), nullable=False, index=True
    )
    item_id: Mapped[int] = mapped_column(ForeignKey("lab_items.id"), nullable=False)
    # pending 已申请 / reported 已出结果
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    requested_by: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    requested_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, nullable=False
    )
    reported_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    result: Mapped[str | None] = mapped_column(String(500), nullable=True)

    item = relationship("LabItem")

    @property
    def item_name(self) -> str:
        return self.item.name if self.item else ""
