from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class TreatmentOrder(Base):
    """门诊治疗处置单（输液/注射/换药/雾化等），开单即计费、护士执行。"""

    __tablename__ = "treatment_orders"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    encounter_id: Mapped[int] = mapped_column(
        ForeignKey("encounters.id"), nullable=False, index=True
    )
    charge_item_id: Mapped[int] = mapped_column(
        ForeignKey("charge_items.id"), nullable=False
    )
    item_name: Mapped[str] = mapped_column(String(100), nullable=False)
    quantity: Mapped[int] = mapped_column(default=1, nullable=False)
    note: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    # pending 待执行 / done 已执行 / cancelled 已取消
    status: Mapped[str] = mapped_column(String(10), default="pending", nullable=False)
    ordered_by: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    ordered_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, nullable=False
    )
    executed_by: Mapped[str | None] = mapped_column(String(50), nullable=True)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
