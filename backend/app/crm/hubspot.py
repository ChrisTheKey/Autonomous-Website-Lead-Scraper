"""
HubSpot CRM integration via hubspot-api-client (HubSpot/hubspot-api-python).
Creates/updates contacts and companies.
"""

import structlog
from hubspot import HubSpot
from hubspot.crm.companies import SimplePublicObjectInputForCreate as CompanyInput
from hubspot.crm.contacts import SimplePublicObjectInputForCreate as ContactInput

from app.core.config import settings

log = structlog.get_logger()

_api = HubSpot(access_token=settings.hubspot_access_token)


async def sync_lead_to_hubspot(lead_id: int) -> dict:
    from app.core.database import AsyncSessionLocal
    from app.models.lead import Lead, LeadStatus

    async with AsyncSessionLocal() as session:
        lead = await session.get(Lead, lead_id)
        if not lead:
            return {"error": "Lead not found"}

    # Create or update company
    company_props = {
        "name": lead.company_name,
        "domain": lead.website,
        "phone": lead.phone or "",
        "city": lead.city or "",
        "country": lead.country or "",
        "description": lead.ai_summary or "",
    }
    company = _api.crm.companies.basic_api.create(
        simple_public_object_input_for_create=CompanyInput(properties=company_props)
    )

    # Create contact if email present
    contact_id = None
    if lead.email:
        contact_props = {
            "email": lead.email,
            "company": lead.company_name,
            "phone": lead.phone or "",
        }
        contact = _api.crm.contacts.basic_api.create(
            simple_public_object_input_for_create=ContactInput(properties=contact_props)
        )
        contact_id = contact.id

    async with AsyncSessionLocal() as session:
        db_lead = await session.get(Lead, lead_id)
        if db_lead:
            db_lead.crm_id = company.id
            db_lead.crm_source = "hubspot"
            db_lead.status = LeadStatus.synced
            await session.commit()

    log.info("hubspot_synced", lead_id=lead_id, company_id=company.id)
    return {"company_id": company.id, "contact_id": contact_id}
