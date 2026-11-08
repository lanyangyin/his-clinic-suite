from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class Drug(Base):
    __tablename__ = "drugs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    spec: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    unit: Mapped[str] = mapped_column(String(20), default="", nullable=False)
    base_price: Mapped[float] = mapped_column(nullable=False)
    # 医保报销比例（0~1；0 表示不在医保目录）
    insurance_ratio: Mapped[float] = mapped_column(
        nullable=False, default=0.7, server_default="0.7"
    )
    # 抗菌药物分级：0 非抗菌药 / 1 非限制使用 / 2 限制使用 / 3 特殊使用
    antibiotic_level: Mapped[int] = mapped_column(
        default=0, server_default="0", nullable=False
    )
