"""
Pipedrive CRM integration via pipedrive/client-nodejs REST API.
Uses HTTPX to call the Pipedrive v1 REST API directly from Python.
"""

import httpx
import structlog

from app.core.config import settings

log = structlog.get_logger()

_BASE = f"https://{settings.pipedrive_company_domain}.pipedrive.com/api/v1"
_HEADERS = {"Content-Type": "application/json"}


async def _post(endpoint: str, payload: dict) -> dict:
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            f"{_BASE}/{endpoint}",
            json=payload,
            params={"api_token": settings.pipedrive_api_key},
            headers=_HEADERS,
        )
        resp.raise_for_status()
        return resp.json()


async def sync_lead_to_pipedrive(lead_id: int) -> dict:
    from app.core.database import AsyncSessionLocal
    from app.models.lead import Lead, LeadStatus

    async with AsyncSessionLocal() as session:
        lead = await session.get(Lead, lead_id)
        if not lead:
            return {"error": "Lead not found"}

    # Create organisation
    org_result = await _post(
        "organizations",
        {
            "name": lead.company_name,
            "address": lead.address or "",
        },
    )
    org_id = org_result.get("data", {}).get("id")

    # Create person (contact)
    person_id = None
    if lead.email or lead.phone:
        person_result = await _post(
            "persons",
            {
                "name": lead.company_name,
                "org_id": org_id,
                "email": [{"value": lead.email, "primary": True}] if lead.email else [],
                "phone": [{"value": lead.phone, "primary": True}] if lead.phone else [],
            },
        )
        person_id = person_result.get("data", {}).get("id")

    # Create deal
    deal_result = await _post(
        "deals",
        {
            "title": f"Lead – {lead.company_name}",
            "org_id": org_id,
            "person_id": person_id,
            "status": "open",
        },
    )
    deal_id = deal_result.get("data", {}).get("id")

    async with AsyncSessionLocal() as session:
        db_lead = await session.get(Lead, lead_id)
        if db_lead:
            db_lead.crm_id = str(deal_id)
            db_lead.crm_source = "pipedrive"
            db_lead.status = LeadStatus.synced
            await session.commit()

    log.info("pipedrive_synced", lead_id=lead_id, deal_id=deal_id)
    return {"org_id": org_id, "person_id": person_id, "deal_id": deal_id}
