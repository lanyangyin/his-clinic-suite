from sqlalchemy import String
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
