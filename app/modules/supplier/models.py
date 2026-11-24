from datetime import date

from sqlalchemy import Boolean, Date, String
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class Supplier(Base):
    __tablename__ = "suppliers"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    contact: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    phone: Mapped[str] = mapped_column(String(20), default="", nullable=False)
    address: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    license_no: Mapped[str] = mapped_column(String(60), default="", nullable=False)
    license_expiry: Mapped[date | None] = mapped_column(Date, nullable=True)
    # active 正常 / suspended 停用 / blacklist 黑名单
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    first_business_approved: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    blacklist_reason: Mapped[str] = mapped_column(String(200), default="", nullable=False)
