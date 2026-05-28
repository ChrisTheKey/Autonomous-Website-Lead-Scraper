from datetime import datetime

from pydantic import BaseModel

from app.models.enums import CompanyStatus, EnrichmentStatus, LeadPriority, LeadSourceType, LeadType


class CompanyOut(BaseModel):
    id: int
    name: str
    industry: str | None
    location: str | None
    address: str | None
    phone: str | None
    website: str | None
    google_place_id: str | None
    website_available: bool
    lead_type: LeadType
    lead_source_type: LeadSourceType
    enrichment_status: EnrichmentStatus
    status: CompanyStatus
    lead_priority: LeadPriority | None
    website_opportunity_score: int
    confidence_score: float
    can_export: bool
    export_block_reason: str | None
    has_https: bool | None
    has_mobile_viewport: bool | None
    has_contact_page: bool | None
    website_reachable: bool | None
    weak_website_reason: str | None
    notes: str | None
    verified_at: datetime | None
    contacted_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CompanyListOut(BaseModel):
    id: int
    name: str
    industry: str | None
    location: str | None
    lead_type: LeadType
    status: CompanyStatus
    lead_priority: LeadPriority | None
    website_opportunity_score: int
    website_available: bool
    phone: str | None
    address: str | None
    can_export: bool
    export_block_reason: str | None

    model_config = {"from_attributes": True}


class CompanyUpdateNotes(BaseModel):
    notes: str
