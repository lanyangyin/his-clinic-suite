from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class InsuranceTransaction(Base):
    """医保事前提醒/交易审计：记录每次开方校验结果与提示。"""

    __tablename__ = "insurance_transactions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    encounter_id: Mapped[int | None] = mapped_column(
        ForeignKey("encounters.id"), nullable=True, index=True
    )
    kind: Mapped[str] = mapped_column(String(20), default="precheck", nullable=False)
    drug_name: Mapped[str] = mapped_column(String(100), default="", nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    ratio: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    result: Mapped[str] = mapped_column(String(20), default="", nullable=False)
    message: Mapped[str] = mapped_column(String(300), default="", nullable=False)
    settlement_no: Mapped[str] = mapped_column(String(60), default="", nullable=False)
    operator: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
