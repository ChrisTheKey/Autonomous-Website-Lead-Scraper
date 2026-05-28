import asyncio

import structlog

from app.tasks.celery_app import celery_app

log = structlog.get_logger()


@celery_app.task(bind=True, name="enrich.lead", max_retries=2)
def enrich_lead_task(self, lead_id: int) -> dict:
    try:
        return asyncio.run(_enrich(lead_id))
    except Exception as exc:
        log.error("enrich_failed", lead_id=lead_id, error=str(exc))
        raise self.retry(exc=exc, countdown=60)


async def _enrich(lead_id: int) -> dict:
    from app.core.database import AsyncSessionLocal
    from app.models.lead import Lead, LeadStatus
    from app.ai.extractor import summarize_lead
    from app.ai.maps_client import geocode_address
    from app.ai.pydantic_ai_agent import research_lead

    async with AsyncSessionLocal() as session:
        lead = await session.get(Lead, lead_id)
        if not lead:
            return {"error": "not found"}

        # Geocode address
        if lead.address and not lead.latitude:
            geo = await geocode_address(lead.address)
            lead.latitude = geo.get("lat")
            lead.longitude = geo.get("lng")

        # AI summary
        summary = await summarize_lead(lead_id)
        lead.ai_summary = summary

        # Pydantic AI research
        info = f"Company: {lead.company_name}\nWebsite: {lead.website}\nSummary: {summary}"
        research = await research_lead(info)
        lead.status = LeadStatus.qualified if research.is_qualified else LeadStatus.rejected

        await session.commit()
        log.info("lead_enriched", lead_id=lead_id, qualified=research.is_qualified)
        return {"lead_id": lead_id, "qualified": research.is_qualified}
