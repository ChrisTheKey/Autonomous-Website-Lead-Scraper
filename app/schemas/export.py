from datetime import datetime

from pydantic import BaseModel

from app.models.enums import LeadSourceType, LeadType


class ExportRow(BaseModel):
    company_name: str
    industry: str | None
    location: str | None
    phone: str | None
    address: str | None
    website_status: str
    lead_type: LeadType
    website_opportunity_score: int
    source_type: LeadSourceType
    verified_at: datetime | None
    notes: str | None
