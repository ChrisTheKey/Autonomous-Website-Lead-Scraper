"""
Salesforce CRM integration via simple-salesforce/simple-salesforce.
Creates Accounts and Leads in Salesforce.
"""

import structlog
from simple_salesforce import Salesforce

from app.core.config import settings

log = structlog.get_logger()

_sf: Salesforce | None = None


def get_sf() -> Salesforce:
    global _sf
    if _sf is None:
        _sf = Salesforce(
            username=settings.salesforce_username,
            password=settings.salesforce_password,
            security_token=settings.salesforce_security_token,
            domain=settings.salesforce_domain,
        )
    return _sf


async def sync_lead_to_salesforce(lead_id: int) -> dict:
    import asyncio
    from app.core.database import AsyncSessionLocal
    from app.models.lead import Lead, LeadStatus

    async with AsyncSessionLocal() as session:
        lead = await session.get(Lead, lead_id)
        if not lead:
            return {"error": "Lead not found"}

    sf = get_sf()

    # Run synchronous simple-salesforce calls in thread pool
    loop = asyncio.get_event_loop()

    account_result = await loop.run_in_executor(
        None,
        lambda: sf.Account.create(
            {
                "Name": lead.company_name,
                "Website": lead.website,
                "Phone": lead.phone or "",
                "BillingCity": lead.city or "",
                "BillingCountry": lead.country or "",
                "Description": lead.ai_summary or "",
            }
        ),
    )
    account_id = account_result.get("id")

    sf_lead_result = await loop.run_in_executor(
        None,
        lambda: sf.Lead.create(
            {
                "Company": lead.company_name,
                "LastName": lead.company_name,
                "Email": lead.email or "",
                "Phone": lead.phone or "",
                "Website": lead.website,
                "City": lead.city or "",
                "Country": lead.country or "",
                "Description": lead.ai_summary or "",
                "LeadSource": "Web Scraper",
            }
        ),
    )
    sf_lead_id = sf_lead_result.get("id")

    async with AsyncSessionLocal() as session:
        db_lead = await session.get(Lead, lead_id)
        if db_lead:
            db_lead.crm_id = sf_lead_id
            db_lead.crm_source = "salesforce"
            db_lead.status = LeadStatus.synced
            await session.commit()

    log.info("salesforce_synced", lead_id=lead_id, sf_lead_id=sf_lead_id)
    return {"account_id": account_id, "lead_id": sf_lead_id}
