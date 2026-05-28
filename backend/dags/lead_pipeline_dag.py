"""
Apache Airflow DAG for scheduled autonomous lead scraping.
Runs daily: Google Maps search → scrape websites → enrich → CRM sync.
"""

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

default_args = {
    "owner": "lead-scraper",
    "depends_on_past": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "email_on_failure": False,
}

SEARCH_QUERIES = [
    ("marketing agency", "Berlin, Germany", 10_000),
    ("software development", "Munich, Germany", 10_000),
    ("ecommerce shop", "Hamburg, Germany", 10_000),
]

TARGET_CRM = "hubspot"


def search_businesses_task(**context) -> list[dict]:
    import asyncio
    import sys

    sys.path.insert(0, "/opt/airflow/backend")
    from app.ai.maps_client import search_businesses

    results = []
    for query, location, radius in SEARCH_QUERIES:
        businesses = asyncio.run(search_businesses(query, location, radius))
        results.extend(businesses)

    context["ti"].xcom_push(key="businesses", value=results)
    return results


def scrape_websites_task(**context) -> list[int]:
    import asyncio
    import sys

    sys.path.insert(0, "/opt/airflow/backend")
    from app.browser.playwright_client import scrape_with_browser
    from app.ai.extractor import extract_lead_data
    from app.core.database import AsyncSessionLocal
    from app.models.lead import Lead

    businesses: list[dict] = context["ti"].xcom_pull(key="businesses", task_ids="search_businesses")
    lead_ids = []

    async def _process(b: dict) -> int | None:
        website = b.get("website")
        if not website:
            return None
        result = await scrape_with_browser(website)
        lead_data = await extract_lead_data(result.html, website)
        async with AsyncSessionLocal() as session:
            from sqlalchemy import select
            existing = await session.execute(select(Lead).where(Lead.website == website))
            if existing.scalar_one_or_none():
                return None
            lead = Lead(
                company_name=lead_data.company_name or b.get("name", ""),
                website=website,
                email=lead_data.email,
                phone=lead_data.phone or b.get("phone"),
                address=lead_data.address or b.get("address"),
                city=lead_data.city,
                country=lead_data.country,
                latitude=b.get("lat"),
                longitude=b.get("lng"),
            )
            session.add(lead)
            await session.commit()
            await session.refresh(lead)
            return lead.id

    for b in businesses[:50]:  # cap per run
        lead_id = asyncio.run(_process(b))
        if lead_id:
            lead_ids.append(lead_id)

    context["ti"].xcom_push(key="lead_ids", value=lead_ids)
    return lead_ids


def enrich_leads_task(**context) -> None:
    import asyncio
    import sys

    sys.path.insert(0, "/opt/airflow/backend")
    from app.tasks.enrich_tasks import _enrich

    lead_ids: list[int] = context["ti"].xcom_pull(key="lead_ids", task_ids="scrape_websites")
    for lead_id in lead_ids:
        asyncio.run(_enrich(lead_id))


def sync_crm_task(**context) -> None:
    import asyncio
    import sys

    sys.path.insert(0, "/opt/airflow/backend")
    from app.tasks.crm_tasks import _sync

    lead_ids: list[int] = context["ti"].xcom_pull(key="lead_ids", task_ids="scrape_websites")
    for lead_id in lead_ids:
        asyncio.run(_sync(lead_id, TARGET_CRM))


with DAG(
    dag_id="autonomous_lead_pipeline",
    default_args=default_args,
    description="Daily autonomous lead scraping, enrichment and CRM sync",
    schedule="0 6 * * *",
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=["leads", "scraping", "crm"],
) as dag:
    t1 = PythonOperator(task_id="search_businesses", python_callable=search_businesses_task)
    t2 = PythonOperator(task_id="scrape_websites", python_callable=scrape_websites_task)
    t3 = PythonOperator(task_id="enrich_leads", python_callable=enrich_leads_task)
    t4 = PythonOperator(task_id="sync_crm", python_callable=sync_crm_task)

    t1 >> t2 >> t3 >> t4
