from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SuppressionEntry(Base):
    __tablename__ = "suppression_list"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id"), index=True)
    domain: Mapped[str | None] = mapped_column(String(500), index=True)
    phone: Mapped[str | None] = mapped_column(String(100), index=True)
    email: Mapped[str | None] = mapped_column(String(500), index=True)
    google_place_id: Mapped[str | None] = mapped_column(String(255), index=True)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
