from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ApprovalEvent(Base):
    """统一审批时间线：不替代各业务表，只记录谁在何时做了什么。"""

    __tablename__ = "approval_events"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    biz_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    biz_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    step: Mapped[str] = mapped_column(String(30), default="review", nullable=False)
    action: Mapped[str] = mapped_column(String(20), nullable=False)
    actor: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    note: Mapped[str] = mapped_column(String(300), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)


class ApprovalRequest(Base):
    """通用审批实例：业务表保留状态，这里保存可配置步骤。"""

    __tablename__ = "approval_requests"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    biz_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    biz_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False, index=True)
    current_step: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    applicant: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    due_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class ApprovalStep(Base):
    __tablename__ = "approval_steps"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    request_id: Mapped[int] = mapped_column(
        ForeignKey("approval_requests.id"), nullable=False, index=True
    )
    step_no: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    role_required: Mapped[str] = mapped_column(String(20), default="pharmacist", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    approver: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    assignee: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    note: Mapped[str] = mapped_column(String(300), default="", nullable=False)
    due_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    acted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class ApprovalFlowStep(Base):
    """按业务类型配置的审批步骤；没有配置时使用单步默认值。"""

    __tablename__ = "approval_flow_steps"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    biz_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    step_no: Mapped[int] = mapped_column(Integer, nullable=False)
    role_required: Mapped[str] = mapped_column(String(20), nullable=False)
    due_hours: Mapped[int] = mapped_column(Integer, default=24, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1", nullable=False)
