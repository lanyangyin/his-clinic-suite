from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
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
    # 高危药品：配药需要第二人核对
    high_alert: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="0", nullable=False
    )
    # 非处方药：允许药房直接零售；处方药必须凭处方
    is_otc: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="0", nullable=False
    )
    # 主要成分/复方成分，用于成分重复提醒；可空
    ingredient: Mapped[str] = mapped_column(
        String(100), default="", server_default="", nullable=False
    )
    # 药品条码（扫码收货/扫码选药），可空
    barcode: Mapped[str] = mapped_column(
        String(50), default="", server_default="", nullable=False
    )
    # 医保贯标：国家医保药品代码（与医保目录对应）
    insurance_code: Mapped[str] = mapped_column(
        String(40), default="", server_default="", nullable=False
    )
    # 医保目录匹配：甲/乙/丙；matched/ambiguous/unmatched
    insurance_category: Mapped[str] = mapped_column(
        String(10), default="", server_default="", nullable=False
    )
    insurance_match_status: Mapped[str] = mapped_column(
        String(20), default="unmatched", server_default="unmatched", nullable=False
    )
    approval_no: Mapped[str] = mapped_column(
        String(60), default="", server_default="", nullable=False
    )
    manufacturer: Mapped[str] = mapped_column(
        String(100), default="", server_default="", nullable=False
    )
    dosage_form: Mapped[str] = mapped_column(
        String(30), default="", server_default="", nullable=False
    )


class DrugInteraction(Base):
    """药品相互作用规则：由管理员维护，不由系统编造临床结论。"""

    __tablename__ = "drug_interactions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    drug_a_id: Mapped[int] = mapped_column(ForeignKey("drugs.id"), nullable=False)
    drug_b_id: Mapped[int] = mapped_column(ForeignKey("drugs.id"), nullable=False)
    # block 禁止同方 / warn 仅提示
    severity: Mapped[str] = mapped_column(
        String(10), default="block", server_default="block", nullable=False
    )
    note: Mapped[str] = mapped_column(
        String(200), default="", server_default="", nullable=False
    )
    active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="1", nullable=False
    )

    drug_a = relationship("Drug", foreign_keys=[drug_a_id])
    drug_b = relationship("Drug", foreign_keys=[drug_b_id])
