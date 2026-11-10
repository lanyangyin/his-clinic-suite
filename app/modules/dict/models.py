from sqlalchemy import Boolean, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class DictEntry(Base):
    __tablename__ = "dict_entries"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    # 字典类型：如 blood_type / pay_type / insurance_type
    dict_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    # 分类：诊断/手术操作/医疗服务项目等（可空，兼容已有字典）
    category: Mapped[str] = mapped_column(
        String(50), default="", server_default="", nullable=False
    )
    sort_order: Mapped[int] = mapped_column(default=0, server_default="0", nullable=False)
    active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="1", nullable=False
    )

    __table_args__ = (
        UniqueConstraint("dict_type", "code", name="uq_dict_type_code"),
    )
