from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class Campus(Base):
    """院区/门诊部（中大型门诊部可能存在多个院区）。"""

    __tablename__ = "campuses"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    address: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Room(Base):
    """诊室：属于某个院区，可关联科室。"""

    __tablename__ = "rooms"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    campus_id: Mapped[int] = mapped_column(ForeignKey("campuses.id"), nullable=False)
    code: Mapped[str] = mapped_column(String(30), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    department_id: Mapped[int | None] = mapped_column(
        ForeignKey("departments.id"), nullable=True
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    __table_args__ = (UniqueConstraint("campus_id", "code", name="uq_room_campus_code"),)
