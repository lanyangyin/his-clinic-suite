from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Stocktake(Base):
    __tablename__ = "stocktakes"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    take_no: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(100), default="", nullable=False)
    # drug 药品 / material 耗材
    kind: Mapped[str] = mapped_column(String(10), nullable=False)
    warehouse: Mapped[str] = mapped_column(String(30), default="总库", nullable=False)
    # counting 盘点中 / completed 已完成 / cancelled 已取消
    status: Mapped[str] = mapped_column(String(20), default="counting", nullable=False)
    note: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    created_by: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    completed_by: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    items: Mapped[list["StocktakeItem"]] = relationship(
        back_populates="take", cascade="all, delete-orphan"
    )


class StocktakeItem(Base):
    __tablename__ = "stocktake_items"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    take_id: Mapped[int] = mapped_column(
        ForeignKey("stocktakes.id"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(10), nullable=False)
    drug_id: Mapped[int | None] = mapped_column(ForeignKey("drugs.id"), nullable=True)
    material_id: Mapped[int | None] = mapped_column(
        ForeignKey("material_items.id"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    spec: Mapped[str] = mapped_column(String(60), default="", nullable=False)
    batch_no: Mapped[str] = mapped_column(String(30), default="", nullable=False)
    warehouse: Mapped[str] = mapped_column(String(30), default="总库", nullable=False)
    book_quantity: Mapped[int] = mapped_column(default=0, nullable=False)
    actual_quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    unit_price: Mapped[float] = mapped_column(default=0.0, nullable=False)

    take: Mapped[Stocktake] = relationship(back_populates="items")

    @property
    def difference(self) -> int | None:
        if self.actual_quantity is None:
            return None
        return self.actual_quantity - self.book_quantity
