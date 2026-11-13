from sqlalchemy import Boolean, String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class Department(Base):
    __tablename__ = "departments"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1", nullable=False)


class Doctor(Base):
    __tablename__ = "doctors"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    department_id: Mapped[int] = mapped_column(
        ForeignKey("departments.id"), nullable=False, index=True
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1", nullable=False)
    # 当前进行中的就诊；只存 ID，避免 doctors/encounters/registrations 外键循环
    current_encounter_id: Mapped[int | None] = mapped_column(nullable=True)
