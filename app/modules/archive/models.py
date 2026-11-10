from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ArchiveRecord(Base):
    """病案归档主表：从建档开始，记录归档、位置、状态。"""

    __tablename__ = "archive_records"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    archive_no: Mapped[str | None] = mapped_column(String(30), unique=True, nullable=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), nullable=False, index=True)
    encounter_id: Mapped[int | None] = mapped_column(
        ForeignKey("encounters.id"), nullable=True, index=True
    )
    # outpatient 门诊 / inpatient 住院 / emergency 急诊
    record_type: Mapped[str] = mapped_column(String(20), default="outpatient", nullable=False)
    page_count: Mapped[int] = mapped_column(default=0, server_default="0", nullable=False)
    # draft 已建档 / archived 已归档 / borrowed 已借出 / sealed 已封存 / destroyed 已销毁
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)
    completeness: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    storage_location: Mapped[str] = mapped_column(String(100), default="", nullable=False)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    archived_by: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    note: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)

    patient = relationship("Patient")
    borrowings: Mapped[list["ArchiveBorrowing"]] = relationship()

    @property
    def patient_name(self) -> str:
        return self.patient.name if self.patient else ""

    @property
    def active_borrowing(self) -> "ArchiveBorrowing | None":
        return next((row for row in self.borrowings if row.status == "borrowed"), None)

    @property
    def active_borrowing_id(self) -> int | None:
        row = self.active_borrowing
        return row.id if row else None


class ArchiveBorrowing(Base):
    __tablename__ = "archive_borrowings"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    record_id: Mapped[int] = mapped_column(
        ForeignKey("archive_records.id"), nullable=False, index=True
    )
    borrower: Mapped[str] = mapped_column(String(50), nullable=False)
    department: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    purpose: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    borrowed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    due_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    returned_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    approver: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    # borrowed 借出中 / returned 已归还 / overdue 逾期
    status: Mapped[str] = mapped_column(String(20), default="borrowed", nullable=False)
    note: Mapped[str] = mapped_column(String(200), default="", nullable=False)


class ArchiveCopyRequest(Base):
    __tablename__ = "archive_copy_requests"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    record_id: Mapped[int] = mapped_column(
        ForeignKey("archive_records.id"), nullable=False, index=True
    )
    applicant: Mapped[str] = mapped_column(String(50), nullable=False)
    id_number: Mapped[str] = mapped_column(String(30), default="", nullable=False)
    relationship: Mapped[str] = mapped_column(String(30), default="本人", nullable=False)
    purpose: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    contents: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    copies: Mapped[int] = mapped_column(default=1, server_default="1", nullable=False)
    fee: Mapped[float] = mapped_column(default=0.0, server_default="0", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    operator: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class ArchiveSeal(Base):
    __tablename__ = "archive_seals"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    record_id: Mapped[int] = mapped_column(
        ForeignKey("archive_records.id"), nullable=False, index=True
    )
    action: Mapped[str] = mapped_column(String(10), nullable=False)  # seal / unseal
    reason: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    witness: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    operator: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)


class ArchiveDestruction(Base):
    __tablename__ = "archive_destructions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    record_id: Mapped[int] = mapped_column(
        ForeignKey("archive_records.id"), nullable=False, index=True
    )
    reason: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    approved_by: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    operator: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    destroyed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    note: Mapped[str] = mapped_column(String(200), default="", nullable=False)

class ArchiveDestructionRequest(Base):
    """病案销毁申请：病案室发起 → 院长审批 → 病案室双人执行。"""

    __tablename__ = "archive_destruction_requests"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    record_id: Mapped[int] = mapped_column(
        ForeignKey("archive_records.id"), nullable=False, index=True
    )
    reason: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    note: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    # pending 待审批 / approved 已批准 / rejected 已驳回 / executed 已执行
    status: Mapped[str] = mapped_column(
        String(20), default="pending", server_default="pending", nullable=False
    )
    requested_by: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    requested_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, nullable=False
    )
    approver: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    approval_note: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    executed_by: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    witness: Mapped[str] = mapped_column(String(50), default="", nullable=False)

    record = relationship("ArchiveRecord")

    @property
    def archive_no(self) -> str:
        return self.record.archive_no or "" if self.record else ""

    @property
    def patient_name(self) -> str:
        return self.record.patient_name if self.record else ""
