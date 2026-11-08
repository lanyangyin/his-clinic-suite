from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class InsuranceMaterial(Base):
    """医保医用耗材目录（本地导入维护）。"""

    __tablename__ = "insurance_materials"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    code: Mapped[str] = mapped_column(
        String(60), unique=True, index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    category: Mapped[str] = mapped_column(
        String(30), default="", server_default="", nullable=False
    )
    spec: Mapped[str] = mapped_column(
        String(80), default="", server_default="", nullable=False
    )
    model: Mapped[str] = mapped_column(
        String(80), default="", server_default="", nullable=False
    )
    manufacturer: Mapped[str] = mapped_column(
        String(100), default="", server_default="", nullable=False
    )
    unit: Mapped[str] = mapped_column(
        String(20), default="", server_default="", nullable=False
    )
    # 耗材 / 器械 / 办公
    material_type: Mapped[str] = mapped_column(
        String(20), default="耗材", server_default="耗材", nullable=False
    )
    registration_no: Mapped[str] = mapped_column(
        String(60), default="", server_default="", nullable=False
    )
    note: Mapped[str] = mapped_column(
        String(200), default="", server_default="", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, nullable=False
    )
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
