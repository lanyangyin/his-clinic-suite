from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class StockMovement(Base):
    """库存流水：每笔入/出都记账（医保进销存与追溯的基础）。"""

    __tablename__ = "stock_movements"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    kind: Mapped[str] = mapped_column(
        String(10), default="drug", server_default="drug", nullable=False
    )
    drug_id: Mapped[int | None] = mapped_column(ForeignKey("drugs.id"), nullable=True)
    material_id: Mapped[int | None] = mapped_column(
        ForeignKey("material_items.id"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    spec: Mapped[str] = mapped_column(
        String(60), default="", server_default="", nullable=False
    )
    unit: Mapped[str] = mapped_column(
        String(20), default="", server_default="", nullable=False
    )
    batch_no: Mapped[str] = mapped_column(
        String(30), default="", server_default="", nullable=False
    )
    expiry: Mapped[date | None] = mapped_column(Date, nullable=True)
    warehouse: Mapped[str] = mapped_column(
        String(30), default="", server_default="", nullable=False
    )
    # in 入库 / out 出库
    direction: Mapped[str] = mapped_column(String(10), nullable=False)
    quantity: Mapped[int] = mapped_column(nullable=False)
    unit_price: Mapped[float] = mapped_column(
        default=0.0, server_default="0", nullable=False
    )
    amount: Mapped[float] = mapped_column(
        default=0.0, server_default="0", nullable=False
    )
    # 该物品/批次在该库房的结存
    balance_after: Mapped[int] = mapped_column(
        default=0, server_default="0", nullable=False
    )
    ref_type: Mapped[str] = mapped_column(
        String(30), default="", server_default="", nullable=False
    )
    ref_id: Mapped[int | None] = mapped_column(nullable=True)
    operator: Mapped[str] = mapped_column(
        String(50), default="", server_default="", nullable=False
    )
    note: Mapped[str] = mapped_column(
        String(200), default="", server_default="", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, nullable=False
    )
