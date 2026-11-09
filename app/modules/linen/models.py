from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class LinenBatch(Base):
    """被服/工作服/窗帘洗涤消毒批次（非无菌器械）。"""

    __tablename__ = "linen_batches"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    batch_no: Mapped[str] = mapped_column(String(30), unique=True, index=True, nullable=False)
    # bedding 床品 / uniform 工作服 / curtain 窗帘隔帘 / other 其他织物
    category: Mapped[str] = mapped_column(String(20), default="bedding", nullable=False)
    item_name: Mapped[str] = mapped_column(String(100), nullable=False)
    quantity: Mapped[int] = mapped_column(nullable=False)
    unit: Mapped[str] = mapped_column(String(20), default="件", nullable=False)
    source_department: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    # normal 普通 / contaminated 污染 / infectious 感染性
    soil_level: Mapped[str] = mapped_column(String(20), default="normal", nullable=False)
    # thermal 热力 / chemical 化学
    wash_method: Mapped[str] = mapped_column(String(20), default="thermal", nullable=False)
    temperature: Mapped[float | None] = mapped_column(nullable=True)
    duration_min: Mapped[int | None] = mapped_column(nullable=True)
    detergent: Mapped[str] = mapped_column(String(100), default="", nullable=False)
    washed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    operator: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    # completed 已完成 / recalled 已召回
    status: Mapped[str] = mapped_column(String(20), default="completed", nullable=False)
    note: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    created_by: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)

    distributions: Mapped[list["LinenDistribution"]] = relationship(
        back_populates="batch", cascade="all, delete-orphan"
    )

    @property
    def distributed_quantity(self) -> int:
        return sum(row.quantity for row in self.distributions)

    @property
    def remaining_quantity(self) -> int:
        return self.quantity - self.distributed_quantity


class LinenDistribution(Base):
    __tablename__ = "linen_distributions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    batch_id: Mapped[int] = mapped_column(
        ForeignKey("linen_batches.id"), nullable=False, index=True
    )
    department: Mapped[str] = mapped_column(String(50), nullable=False)
    quantity: Mapped[int] = mapped_column(nullable=False)
    distributed_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, nullable=False
    )
    distributed_by: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    note: Mapped[str] = mapped_column(String(200), default="", nullable=False)

    batch: Mapped[LinenBatch] = relationship(back_populates="distributions")


class CurtainRecord(Base):
    """窗帘/隔帘拆洗生命周期记录（不进入无菌器械流程）。"""

    __tablename__ = "curtain_records"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    department: Mapped[str] = mapped_column(String(50), nullable=False)
    room: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    curtain_no: Mapped[str] = mapped_column(String(50), nullable=False)
    # remove 拆下 / wash 洗涤消毒 / reinstall 安装
    event: Mapped[str] = mapped_column(String(20), nullable=False)
    event_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    method: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    operator: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    next_due: Mapped[date | None] = mapped_column(Date, nullable=True)
    note: Mapped[str] = mapped_column(String(200), default="", nullable=False)
