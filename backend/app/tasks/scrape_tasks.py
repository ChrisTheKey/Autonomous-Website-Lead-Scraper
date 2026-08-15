import asyncio
from urllib.parse import urlparse

import structlog
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings

from app.ai.scrapegraph_client import RobotsDisallowedError, ScrapeGraphUnavailableError
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


@celery_app.task(bind=True, name="scrape.scrapegraph", max_retries=3)
def run_scrapegraph_task(self, url: str, prompt: str | None = None) -> dict:
    """Scrape a URL with ScrapeGraphAI and persist the extracted lead."""

    try:
        return asyncio.run(_scrapegraph_scrape(url, prompt))
    except RobotsDisallowedError:
        log.info("scrapegraph_skipped_robots", url=url)
        return {"url": url, "method": "scrapegraphai", "status": "skipped_robots"}
    except ScrapeGraphUnavailableError as exc:
        # A missing dependency will not fix itself on retry.
        log.error("scrapegraph_unavailable", url=url, error=str(exc))
        raise
    except Exception as exc:
        log.error("scrapegraph_scrape_failed", url=url, error=str(exc))
        raise self.retry(exc=exc, countdown=2**self.request.retries * 30)


async def _scrapegraph_scrape(url: str, prompt: str | None) -> dict:
    from app.ai.scrapegraph_client import DEFAULT_LEAD_PROMPT, scrape_lead
    from app.core.database import AsyncSessionLocal
    from app.models.lead import Lead

    lead_data = await scrape_lead(url, prompt or DEFAULT_LEAD_PROMPT)

    async with AsyncSessionLocal() as session:
        lead = Lead(
            company_name=lead_data.company_name or urlparse(url).netloc,
            website=url,
            email=lead_data.email,
            phone=lead_data.phone,
            address=lead_data.address,
            city=lead_data.city,
            country=lead_data.country,
            description=lead_data.description,
            source_url=url,
        )
        session.add(lead)
        await session.commit()
        await session.refresh(lead)
        return {"url": url, "method": "scrapegraphai", "lead_id": lead.id, "status": "done"}


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
    from app.ai.extractor import extract_lead_data
    from app.browser.playwright_client import scrape_with_browser
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
