from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class DrugTraceCode(Base):
    """药品追溯码：一盒一码，随入库/出库/发药/退药流转。"""

    __tablename__ = "drug_trace_codes"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    trace_code: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, nullable=False
    )
    drug_id: Mapped[int] = mapped_column(ForeignKey("drugs.id"), nullable=False, index=True)
    batch_no: Mapped[str] = mapped_column(
        String(30), default="", server_default="", nullable=False
    )
    # 当前所在库房：总库 / 药房
    warehouse: Mapped[str] = mapped_column(
        String(30), default="总库", server_default="总库", nullable=False
    )
    # in_stock 在库 / used 已使用 / returned 已退回 / void 作废
    status: Mapped[str] = mapped_column(
        String(20), default="in_stock", server_default="in_stock", nullable=False
    )
    ref_type: Mapped[str] = mapped_column(
        String(20), default="", server_default="", nullable=False
    )
    ref_id: Mapped[int | None] = mapped_column(nullable=True)
    patient_id: Mapped[int | None] = mapped_column(nullable=True)
    encounter_id: Mapped[int | None] = mapped_column(nullable=True)
    scanned_by: Mapped[str] = mapped_column(
        String(50), default="", server_default="", nullable=False
    )
    scanned_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, nullable=False
    )
    note: Mapped[str] = mapped_column(
        String(200), default="", server_default="", nullable=False
    )
