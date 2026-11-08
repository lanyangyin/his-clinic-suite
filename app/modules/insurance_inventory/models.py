from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class InsuranceInventoryUpload(Base):
    """医保进销存上传批次：记录期间、条数、金额、报文与回执。"""

    __tablename__ = "insurance_inventory_uploads"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    upload_no: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    record_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    total_amount: Mapped[float] = mapped_column(
        Float, default=0.0, server_default="0", nullable=False
    )
    # submitted 已提交 / success 成功 / failed 失败
    status: Mapped[str] = mapped_column(
        String(20), default="submitted", server_default="submitted", nullable=False
    )
    payload: Mapped[str] = mapped_column(
        Text, default="", server_default="", nullable=False
    )
    response: Mapped[str] = mapped_column(
        Text, default="", server_default="", nullable=False
    )
    created_by: Mapped[str] = mapped_column(
        String(50), default="", server_default="", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, nullable=False
    )
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
