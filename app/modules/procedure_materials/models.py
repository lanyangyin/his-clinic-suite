from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ProcedureMaterial(Base):
    """手术/治疗室耗材使用：扣减库房库存并计材料费。"""

    __tablename__ = "procedure_materials"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    # surgery / treatment_room
    source_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    source_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    encounter_id: Mapped[int | None] = mapped_column(
        ForeignKey("encounters.id"), nullable=True
    )
    material_id: Mapped[int] = mapped_column(
        ForeignKey("material_items.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    quantity: Mapped[int] = mapped_column(nullable=False)
    unit_price: Mapped[float] = mapped_column(default=0.0, nullable=False)
    amount: Mapped[float] = mapped_column(default=0.0, nullable=False)
    warehouse: Mapped[str] = mapped_column(String(30), default="总库", nullable=False)
    operator: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    returned_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)

    material = relationship("MaterialItem")
