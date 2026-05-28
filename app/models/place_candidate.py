from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import ReviewStatus


class PlaceCandidate(Base):
    __tablename__ = "place_candidates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    search_id: Mapped[int] = mapped_column(ForeignKey("searches.id"), nullable=False, index=True)
    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id"), index=True)

    # Google Places data (stored per ToS: place_id + metadata only)
    google_place_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    has_website: Mapped[bool] = mapped_column(Boolean, default=False)
    website_uri: Mapped[str | None] = mapped_column(String(2000))
    phone_available: Mapped[bool] = mapped_column(Boolean, default=False)
    address_available: Mapped[bool] = mapped_column(Boolean, default=False)
    business_status: Mapped[str | None] = mapped_column(String(100))
    types: Mapped[list | None] = mapped_column(JSONB)
    rating: Mapped[float | None] = mapped_column(Float)
    user_rating_count: Mapped[int | None] = mapped_column(Integer)

    # Privacy: we store a hash of the raw payload, not the payload itself
    raw_payload_hash: Mapped[str | None] = mapped_column(String(64))

    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    review_status: Mapped[ReviewStatus] = mapped_column(
        Enum(ReviewStatus, name="reviewstatus"), default=ReviewStatus.pending
    )
    notes: Mapped[str | None] = mapped_column(Text)

    search: Mapped["Search"] = relationship(back_populates="place_candidates")  # type: ignore[name-defined]
    company: Mapped["Company | None"] = relationship(back_populates="place_candidates")  # type: ignore[name-defined]
