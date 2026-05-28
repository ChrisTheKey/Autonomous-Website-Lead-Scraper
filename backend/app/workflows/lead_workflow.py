"""
Temporal workflow for end-to-end autonomous lead processing.
Orchestrates: scrape → AI enrich → qualify → CRM sync
"""

from datetime import timedelta

from temporalio import activity, workflow
from temporalio.common import RetryPolicy


# ── Activities ────────────────────────────────────────────────────────────────

@activity.defn
async def scrape_website_activity(url: str, use_browser: bool) -> dict:
    if use_browser:
        from app.browser.playwright_client import scrape_with_browser
        from app.ai.extractor import extract_lead_data
        from app.core.database import AsyncSessionLocal
        from app.models.lead import Lead

        result = await scrape_with_browser(url)
        lead_data = await extract_lead_data(result.html, url)
        async with AsyncSessionLocal() as session:
            lead = Lead(
                company_name=lead_data.company_name,
                website=url,
                email=lead_data.email,
                phone=lead_data.phone,
                address=lead_data.address,
                city=lead_data.city,
                country=lead_data.country,
                raw_html=result.html[:50_000],
            )
            session.add(lead)
            await session.commit()
            await session.refresh(lead)
            return {"lead_id": lead.id}
    else:
        from app.tasks.scrape_tasks import _scrapy_scrape
        return _scrapy_scrape(url, depth=1)


@activity.defn
async def enrich_lead_activity(lead_id: int) -> dict:
    from app.tasks.enrich_tasks import _enrich
    return await _enrich(lead_id)


@activity.defn
async def sync_crm_activity(lead_id: int, crm: str) -> dict:
    from app.tasks.crm_tasks import _sync
    return await _sync(lead_id, crm)


# ── Workflow ──────────────────────────────────────────────────────────────────

@workflow.defn
class LeadProcessingWorkflow:
    @workflow.run
    async def run(self, url: str, use_browser: bool = False, crm: str = "hubspot") -> dict:
        retry = RetryPolicy(maximum_attempts=3, initial_interval=timedelta(seconds=10))

        # Step 1: Scrape
        scrape_result = await workflow.execute_activity(
            scrape_website_activity,
            args=[url, use_browser],
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=retry,
        )
        lead_id = scrape_result.get("lead_id")
        if not lead_id:
            return {"error": "Scrape produced no lead", "url": url}

        # Step 2: Enrich + qualify
        enrich_result = await workflow.execute_activity(
            enrich_lead_activity,
            args=[lead_id],
            start_to_close_timeout=timedelta(minutes=3),
            retry_policy=retry,
        )

        if not enrich_result.get("qualified"):
            return {"lead_id": lead_id, "status": "rejected"}

        # Step 3: CRM sync
        crm_result = await workflow.execute_activity(
            sync_crm_activity,
            args=[lead_id, crm],
            start_to_close_timeout=timedelta(minutes=2),
            retry_policy=retry,
        )

        return {"lead_id": lead_id, "status": "synced", "crm": crm_result}
