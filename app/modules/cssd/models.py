from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class InstrumentSet(Base):
    """可复用器械包/诊疗包主数据（不包含被服）。"""

    __tablename__ = "instrument_sets"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    code: Mapped[str] = mapped_column(String(30), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    department: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    note: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)


class SterilizationBatch(Base):
    """一锅/一个灭菌循环；放行前必须有合格的化学/生物监测。"""

    __tablename__ = "sterilization_batches"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    batch_no: Mapped[str] = mapped_column(String(30), unique=True, index=True, nullable=False)
    sterilizer: Mapped[str] = mapped_column(String(50), nullable=False)
    # steam 高压蒸汽 / plasma 低温等离子 / chemical 化学浸泡
    method: Mapped[str] = mapped_column(String(20), default="steam", nullable=False)
    cycle: Mapped[str] = mapped_column(String(30), default="", nullable=False)
    temperature: Mapped[float | None] = mapped_column(nullable=True)
    pressure: Mapped[float | None] = mapped_column(nullable=True)
    duration_min: Mapped[int | None] = mapped_column(nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    operator: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    chemical_indicator: Mapped[str] = mapped_column(String(10), default="pending", nullable=False)
    biological_indicator: Mapped[str] = mapped_column(String(10), default="pending", nullable=False)
    # pending 待放行 / released 已放行 / rejected 不合格
    release_status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    released_by: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    released_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    note: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)

    packages: Mapped[list["InstrumentPackage"]] = relationship(back_populates="batch")


class InstrumentPackage(Base):
    """单个灭菌包，按包码追溯到患者/手术/科室。"""

    __tablename__ = "instrument_packages"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    package_code: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    set_id: Mapped[int] = mapped_column(ForeignKey("instrument_sets.id"), nullable=False)
    batch_id: Mapped[int] = mapped_column(ForeignKey("sterilization_batches.id"), nullable=False)
    sterilized_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    expiry: Mapped[date] = mapped_column(Date, nullable=False)
    # sterilized 已灭菌 / issued 已发放 / used 已使用 / recalled 已召回
    status: Mapped[str] = mapped_column(String(20), default="sterilized", nullable=False)
    location: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    surgery_case_id: Mapped[int | None] = mapped_column(
        ForeignKey("surgery_cases.id"), nullable=True
    )
    note: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)

    set: Mapped[InstrumentSet] = relationship()
    batch: Mapped[SterilizationBatch] = relationship(back_populates="packages")
    usages: Mapped[list["PackageUsage"]] = relationship(
        back_populates="package", cascade="all, delete-orphan"
    )

    @property
    def set_name(self) -> str:
        return self.set.name if self.set else ""

    @property
    def batch_no(self) -> str:
        return self.batch.batch_no if self.batch else ""


class PackageUsage(Base):
    """器械包使用去向：科室/患者/就诊。"""

    __tablename__ = "package_usages"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    package_id: Mapped[int] = mapped_column(
        ForeignKey("instrument_packages.id"), nullable=False, index=True
    )
    department: Mapped[str] = mapped_column(String(50), nullable=False)
    patient_id: Mapped[int | None] = mapped_column(ForeignKey("patients.id"), nullable=True)
    encounter_id: Mapped[int | None] = mapped_column(ForeignKey("encounters.id"), nullable=True)
    used_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    used_by: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    note: Mapped[str] = mapped_column(String(200), default="", nullable=False)

    package: Mapped[InstrumentPackage] = relationship(back_populates="usages")
