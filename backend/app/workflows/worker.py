"""
Temporal worker entrypoint — run with: python -m app.workflows.worker
"""

import asyncio

from temporalio.client import Client
from temporalio.worker import Worker

from app.core.config import settings
from app.workflows.lead_workflow import (
    LeadProcessingWorkflow,
    enrich_lead_activity,
    scrape_website_activity,
    sync_crm_activity,
)


async def main() -> None:
    client = await Client.connect(settings.temporal_host, namespace=settings.temporal_namespace)
    worker = Worker(
        client,
        task_queue="lead-processing",
        workflows=[LeadProcessingWorkflow],
        activities=[scrape_website_activity, enrich_lead_activity, sync_crm_activity],
    )
    print(f"Temporal worker started on {settings.temporal_host}")
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
