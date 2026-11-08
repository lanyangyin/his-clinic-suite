from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class MaterialItem(Base):
    __tablename__ = "material_items"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    spec: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    unit: Mapped[str] = mapped_column(String(20), default="", nullable=False)
    price: Mapped[float] = mapped_column(default=0.0, server_default="0", nullable=False)
    # 高值耗材：需要按序列号追溯
    is_high_value: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="0", nullable=False
    )
    # 分类：consumable 耗材 / device 医疗器械 / office 办公用品 / other 其他
    category: Mapped[str] = mapped_column(
        String(20), default="consumable", server_default="consumable", nullable=False
    )
    manufacturer: Mapped[str] = mapped_column(
        String(100), default="", server_default="", nullable=False
    )
    # 医疗器械注册证/备案号
    registration_no: Mapped[str] = mapped_column(
        String(60), default="", server_default="", nullable=False
    )


class MaterialStock(Base):
    __tablename__ = "material_stocks"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    item_id: Mapped[int] = mapped_column(
        ForeignKey("material_items.id"), nullable=False, index=True
    )
    # 库房标识：如 总库 / 骨科病区
    warehouse: Mapped[str] = mapped_column(String(30), nullable=False)
    quantity: Mapped[int] = mapped_column(default=0, server_default="0", nullable=False)

    __table_args__ = (
        UniqueConstraint("item_id", "warehouse", name="uq_material_item_warehouse"),
    )

    item = relationship("MaterialItem")

    @property
    def item_name(self) -> str:
        return self.item.name if self.item else ""


class MaterialUsage(Base):
    __tablename__ = "material_usages"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    item_id: Mapped[int] = mapped_column(
        ForeignKey("material_items.id"), nullable=False, index=True
    )
    # 高值耗材序列号（全局唯一，用于追溯使用去向）
    serial_no: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    encounter_id: Mapped[int] = mapped_column(
        ForeignKey("encounters.id"), nullable=False
    )
    warehouse: Mapped[str] = mapped_column(String(30), default="", nullable=False)
    used_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, nullable=False
    )
    used_by: Mapped[str] = mapped_column(String(50), default="", nullable=False)

    item = relationship("MaterialItem")

    @property
    def item_name(self) -> str:
        return self.item.name if self.item else ""
