from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class LabItem(Base):
    __tablename__ = "lab_items"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    price: Mapped[float] = mapped_column(default=0.0, server_default="0", nullable=False)
    # 标本类型（血液/尿液/粪便/痰/分泌物等）
    specimen_type: Mapped[str] = mapped_column(
        String(30), default="血液", server_default="血液", nullable=False
    )
    unit: Mapped[str] = mapped_column(String(20), default="", server_default="", nullable=False)
    reference_low: Mapped[float | None] = mapped_column(Float, nullable=True)
    reference_high: Mapped[float | None] = mapped_column(Float, nullable=True)
    method: Mapped[str] = mapped_column(String(50), default="", server_default="", nullable=False)
    tat_minutes: Mapped[int] = mapped_column(default=60, server_default="60", nullable=False)
    insurance_ratio: Mapped[float] = mapped_column(
        default=0.7, server_default="0.7", nullable=False
    )
    result_kind: Mapped[str] = mapped_column(
        String(10), default="numeric", server_default="numeric", nullable=False
    )


class LabRequest(Base):
    __tablename__ = "lab_requests"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    encounter_id: Mapped[int] = mapped_column(
        ForeignKey("encounters.id"), nullable=False, index=True
    )
    item_id: Mapped[int] = mapped_column(ForeignKey("lab_items.id"), nullable=False)
    # pending 待采样 / collected 已采样 / received 已签收 / testing 检验中
    # reported 已报告 / reviewed 已审核 / rejected 标本拒收 / cancelled 已取消
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    priority: Mapped[str] = mapped_column(
        String(10), default="routine", server_default="routine", nullable=False
    )
    specimen_no: Mapped[str | None] = mapped_column(String(40), unique=True, nullable=True)
    specimen_type: Mapped[str] = mapped_column(
        String(30), default="血液", server_default="血液", nullable=False
    )
    requested_by: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    requested_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, nullable=False
    )
    collected_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    collected_by: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    received_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    received_by: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    testing_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    testing_by: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    reported_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    report_no: Mapped[str | None] = mapped_column(String(30), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reviewed_by: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    reject_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # 结构化结果（数值型项目）；result 保留文本摘要/兼容旧数据
    result: Mapped[str | None] = mapped_column(String(500), nullable=True)
    result_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    result_unit: Mapped[str] = mapped_column(String(20), default="", nullable=False)
    reference_low: Mapped[float | None] = mapped_column(Float, nullable=True)
    reference_high: Mapped[float | None] = mapped_column(Float, nullable=True)
    abnormal_flag: Mapped[str] = mapped_column(
        String(10), default="", server_default="", nullable=False
    )
    critical_flag: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="0", nullable=False
    )
    critical_note: Mapped[str | None] = mapped_column(String(200), nullable=True)
    critical_notified_to: Mapped[str | None] = mapped_column(String(100), nullable=True)
    critical_notified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    item = relationship("LabItem")

    @property
    def item_name(self) -> str:
        return self.item.name if self.item else ""

    @property
    def result_display(self) -> str:
        if self.result_value is not None:
            value = f"{self.result_value:g}"
            if self.result_unit:
                value += f" {self.result_unit}"
            return value
        return self.result or ""

