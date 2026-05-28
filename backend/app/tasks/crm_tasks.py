import asyncio

import structlog

from app.tasks.celery_app import celery_app

log = structlog.get_logger()


@celery_app.task(bind=True, name="crm.sync", max_retries=3)
def sync_crm_task(self, lead_id: int, crm: str) -> dict:
    try:
        return asyncio.run(_sync(lead_id, crm))
    except Exception as exc:
        log.error("crm_sync_failed", lead_id=lead_id, crm=crm, error=str(exc))
        raise self.retry(exc=exc, countdown=2**self.request.retries * 60)


async def _sync(lead_id: int, crm: str) -> dict:
    from app.crm.hubspot import sync_lead_to_hubspot
    from app.crm.pipedrive import sync_lead_to_pipedrive
    from app.crm.salesforce import sync_lead_to_salesforce

    crm = crm.lower()
    if crm == "hubspot":
        return await sync_lead_to_hubspot(lead_id)
    if crm == "pipedrive":
        return await sync_lead_to_pipedrive(lead_id)
    if crm == "salesforce":
        return await sync_lead_to_salesforce(lead_id)
    return {"error": f"Unknown CRM: {crm}"}
