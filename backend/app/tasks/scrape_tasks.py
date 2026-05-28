import asyncio

import structlog
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings

from app.tasks.celery_app import celery_app

log = structlog.get_logger()


@celery_app.task(bind=True, name="scrape.run", max_retries=3)
def run_scrape_task(self, url: str, use_browser: bool = False, depth: int = 1) -> dict:
    try:
        if use_browser:
            result = asyncio.run(_browser_scrape(url))
        else:
            result = _scrapy_scrape(url, depth)
        return result
    except Exception as exc:
        log.error("scrape_failed", url=url, error=str(exc))
        raise self.retry(exc=exc, countdown=2**self.request.retries * 30)


def _scrapy_scrape(url: str, depth: int) -> dict:
    from app.scrapers.spiders.lead_spider import LeadSpider

    settings = get_project_settings()
    settings.setmodule("app.scrapers.settings")
    settings.set("DEPTH_LIMIT", depth)

    process = CrawlerProcess(settings)
    process.crawl(LeadSpider, start_url=url)
    process.start()
    return {"url": url, "method": "scrapy", "status": "done"}


async def _browser_scrape(url: str) -> dict:
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
            email=lead_data.email or (result.emails[0] if result.emails else None),
            phone=lead_data.phone or (result.phones[0] if result.phones else None),
            address=lead_data.address,
            city=lead_data.city,
            country=lead_data.country,
            description=lead_data.description,
            raw_html=result.html[:50_000],
        )
        session.add(lead)
        await session.commit()
        await session.refresh(lead)
        return {"url": url, "method": "playwright", "lead_id": lead.id, "status": "done"}


# Re-export for import convenience in routes
run_scrape_task  # noqa: F401
