from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import ContactReviewStatus


class Contact(Base):
    __tablename__ = "contacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)

    # Only publicly visible business data — never guessed
    full_name: Mapped[str | None] = mapped_column(String(500))
    role: Mapped[str | None] = mapped_column(String(255))
    email: Mapped[str | None] = mapped_column(String(500))
    phone: Mapped[str | None] = mapped_column(String(100))

    # Provenance — mandatory for any personal data
    source_url: Mapped[str | None] = mapped_column(Text)
    source_type: Mapped[str] = mapped_column(String(100), nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0)

    # Privacy flag — blocks export if True and no source_url
    is_personal_data: Mapped[bool] = mapped_column(Boolean, default=False)

    review_status: Mapped[ContactReviewStatus] = mapped_column(
        Enum(ContactReviewStatus, name="contactreviewstatus"),
        default=ContactReviewStatus.needs_review,
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    company: Mapped["Company"] = relationship(back_populates="contacts")  # type: ignore[name-defined]
