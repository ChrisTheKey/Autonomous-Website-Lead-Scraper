from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Search(Base):
    __tablename__ = "searches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    industry: Mapped[str] = mapped_column(String(255), nullable=False)
    location: Mapped[str] = mapped_column(String(255), nullable=False)
    radius_km: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    keywords: Mapped[list | None] = mapped_column(JSONB, default=list)
    target: Mapped[str] = mapped_column(String(50), default="no_website")
    max_results: Mapped[int] = mapped_column(Integer, default=100)
    status: Mapped[str] = mapped_column(String(50), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    companies: Mapped[list["Company"]] = relationship(back_populates="search", lazy="select")  # type: ignore[name-defined]
    place_candidates: Mapped[list["PlaceCandidate"]] = relationship(back_populates="search", lazy="select")  # type: ignore[name-defined]
