from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class NarcoticLedger(Base):
    """麻精专用账册：发药、退药、空安瓿回收逐笔记录。"""

    __tablename__ = "narcotic_ledger"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    drug_id: Mapped[int | None] = mapped_column(ForeignKey("drugs.id"), nullable=True, index=True)
    drug_name: Mapped[str] = mapped_column(String(100), default="", nullable=False)
    prescription_id: Mapped[int | None] = mapped_column(ForeignKey("prescriptions.id"), nullable=True, index=True)
    dispense_id: Mapped[int | None] = mapped_column(ForeignKey("dispensations.id"), nullable=True, index=True)
    patient_id: Mapped[int | None] = mapped_column(ForeignKey("patients.id"), nullable=True, index=True)
    batch_no: Mapped[str] = mapped_column(String(30), default="", nullable=False)
    # issue 发药 / return 退药 / ampoule_return 空安瓿回收
    action: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    operator: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    witness: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    note: Mapped[str] = mapped_column(String(300), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)


class NarcoticInventoryCheck(Base):
    """麻精盘点：账面数 vs 实盘数，差异需审批后调整库存。"""

    __tablename__ = "narcotic_inventory_checks"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    drug_id: Mapped[int] = mapped_column(ForeignKey("drugs.id"), nullable=False, index=True)
    drug_name: Mapped[str] = mapped_column(String(100), default="", nullable=False)
    batch_no: Mapped[str] = mapped_column(String(30), default="", nullable=False)
    expected_qty: Mapped[int] = mapped_column(Integer, nullable=False)
    counted_qty: Mapped[int] = mapped_column(Integer, nullable=False)
    difference: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(String(300), default="", nullable=False)
    # pending / approved / rejected
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False, index=True)
    checked_by: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    approved_by: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
