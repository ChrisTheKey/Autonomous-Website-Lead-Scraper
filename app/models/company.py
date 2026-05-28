from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import (
    CompanyStatus,
    EnrichmentStatus,
    LeadPriority,
    LeadSourceType,
    LeadType,
)


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    search_id: Mapped[int | None] = mapped_column(ForeignKey("searches.id"), index=True)

    # Identity
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    normalized_name: Mapped[str | None] = mapped_column(String(500), index=True)
    industry: Mapped[str | None] = mapped_column(String(255))
    location: Mapped[str | None] = mapped_column(String(255))
    address: Mapped[str | None] = mapped_column(Text)
    phone: Mapped[str | None] = mapped_column(String(100))
    website: Mapped[str | None] = mapped_column(String(2000))
    normalized_domain: Mapped[str | None] = mapped_column(String(500), index=True)
    google_place_id: Mapped[str | None] = mapped_column(String(255), unique=True, index=True)

    # Lead classification
    website_available: Mapped[bool] = mapped_column(Boolean, default=False)
    lead_type: Mapped[LeadType] = mapped_column(
        Enum(LeadType, name="leadtype"), default=LeadType.invalid_or_risky, index=True
    )
    lead_source_type: Mapped[LeadSourceType] = mapped_column(
        Enum(LeadSourceType, name="leadsourcetype"), default=LeadSourceType.google_places
    )
    enrichment_status: Mapped[EnrichmentStatus] = mapped_column(
        Enum(EnrichmentStatus, name="enrichmentstatus"), default=EnrichmentStatus.discovered, index=True
    )
    status: Mapped[CompanyStatus] = mapped_column(
        Enum(CompanyStatus, name="companystatus"), default=CompanyStatus.discovered, index=True
    )
    lead_priority: Mapped[LeadPriority | None] = mapped_column(
        Enum(LeadPriority, name="leadpriority"), index=True
    )

    # Scoring
    website_opportunity_score: Mapped[int] = mapped_column(Integer, default=0)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0)

    # Compliance
    can_export: Mapped[bool] = mapped_column(Boolean, default=False)
    export_block_reason: Mapped[str | None] = mapped_column(String(500))
    data_origin: Mapped[str | None] = mapped_column(String(255))
    data_retention_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Website quality signals (cached from analysis)
    has_https: Mapped[bool | None] = mapped_column(Boolean)
    has_mobile_viewport: Mapped[bool | None] = mapped_column(Boolean)
    has_contact_page: Mapped[bool | None] = mapped_column(Boolean)
    website_reachable: Mapped[bool | None] = mapped_column(Boolean)
    weak_website_reason: Mapped[str | None] = mapped_column(String(500))

    # Google data TTL
    google_data_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Review
    notes: Mapped[str | None] = mapped_column(Text)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    contacted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    search: Mapped["Search | None"] = relationship(back_populates="companies")  # type: ignore[name-defined]
    place_candidates: Mapped[list["PlaceCandidate"]] = relationship(back_populates="company", lazy="select")  # type: ignore[name-defined]
    crawled_pages: Mapped[list["CrawledPage"]] = relationship(back_populates="company", lazy="select")  # type: ignore[name-defined]
    contacts: Mapped[list["Contact"]] = relationship(back_populates="company", lazy="select")  # type: ignore[name-defined]
