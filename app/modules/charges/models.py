from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class ChargeItem(Base):
    """收费项目字典（挂号费/诊疗费/治疗费/其他非药品、非检验检查项目）。"""

    __tablename__ = "charge_items"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    # registration 挂号 / consultation 诊疗 / lab 检验 / imaging 检查 / treatment 治疗 / other 其他
    category: Mapped[str] = mapped_column(String(20), default="other", nullable=False)
    price: Mapped[float] = mapped_column(default=0.0, server_default="0", nullable=False)
    insurance_ratio: Mapped[float] = mapped_column(
        default=0.7, server_default="0.7", nullable=False
    )
    active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="1", nullable=False
    )


class EncounterCharge(Base):
    """就诊费用明细：一次就诊的挂号/诊疗/药品/检验/检查/治疗费用。"""

    __tablename__ = "encounter_charges"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    encounter_id: Mapped[int] = mapped_column(
        ForeignKey("encounters.id"), nullable=False, index=True
    )
    # 来源：registration / encounter / prescription / lab_request / imaging_request / treatment
    source_type: Mapped[str] = mapped_column(String(30), nullable=False)
    source_id: Mapped[int] = mapped_column(nullable=False)
    charge_type: Mapped[str] = mapped_column(String(20), nullable=False)
    charge_item_id: Mapped[int | None] = mapped_column(
        ForeignKey("charge_items.id"), nullable=True
    )
    drug_id: Mapped[int | None] = mapped_column(ForeignKey("drugs.id"), nullable=True)
    item_name: Mapped[str] = mapped_column(String(100), nullable=False)
    quantity: Mapped[int] = mapped_column(nullable=False)
    unit_price: Mapped[float] = mapped_column(nullable=False)
    amount: Mapped[float] = mapped_column(nullable=False)
    insurance_ratio: Mapped[float] = mapped_column(
        default=0.7, server_default="0.7", nullable=False
    )
    # pending 待收 / paid 已收 / partially_refunded 部分退费 / refunded 已退
    status: Mapped[str] = mapped_column(String(30), default="pending", nullable=False)
    # 已退数量（支持按颗/按项部分退费）
    refunded_quantity: Mapped[int] = mapped_column(
        default=0, server_default="0", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, nullable=False
    )

    __table_args__ = (
        UniqueConstraint("source_type", "source_id", name="uq_charge_source"),
    )
