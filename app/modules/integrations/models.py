from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class IntegrationConfig(Base):
    __tablename__ = "integration_configs"

    key: Mapped[str] = mapped_column(String(60), primary_key=True)
    value: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    updated_by: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
