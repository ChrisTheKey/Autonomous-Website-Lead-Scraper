"""
Celery tasks for async lead processing.

Each task is idempotent and writes audit logs on completion/failure.
"""

from __future__ import annotations

import asyncio
import ssl
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode

import structlog
from celery import Celery

from app.config import settings


def _clean_redis_url(url: str) -> str:
    """Strip SSL query params from URL; SSL is controlled via broker_use_ssl."""
    parsed = urlparse(url)
    params = {k: v[0] for k, v in parse_qs(parsed.query).items()
              if k not in ("ssl_cert_reqs", "ssl")}
    return urlunparse(parsed._replace(query=urlencode(params)))


_is_rediss = settings.celery_broker_url.startswith("rediss://")
_broker_url = _clean_redis_url(settings.celery_broker_url) if _is_rediss else settings.celery_broker_url
_backend_url = _clean_redis_url(settings.celery_result_backend) if settings.celery_result_backend.startswith("rediss://") else settings.celery_result_backend
_ssl_opts = {"ssl_cert_reqs": ssl.CERT_NONE} if _is_rediss else {}

log = structlog.get_logger()

celery_app = Celery(
    "lead_discovery",
    broker=_broker_url,
    backend=_backend_url,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    worker_prefetch_multiplier=1,
    broker_use_ssl=_ssl_opts or None,
    redis_backend_use_ssl=_ssl_opts or None,
    task_routes={
        "app.workers.tasks.run_search_task": {"queue": "search"},
        "app.workers.tasks.crawl_company_task": {"queue": "crawl"},
        "app.workers.tasks.analyse_website_task": {"queue": "analyse"},
        "app.workers.tasks.refresh_company_task": {"queue": "refresh"},
    },
)


@celery_app.task(bind=True, name="run_search_task", max_retries=2)
def run_search_task(self, search_id: int) -> dict:
    return asyncio.run(_run_search(search_id))


@celery_app.task(bind=True, name="crawl_company_task", max_retries=3)
def crawl_company_task(self, company_id: int) -> dict:
    return asyncio.run(_crawl_company(company_id))


@celery_app.task(bind=True, name="analyse_website_task", max_retries=2)
def analyse_website_task(self, company_id: int) -> dict:
    return asyncio.run(_analyse_website(company_id))


@celery_app.task(bind=True, name="refresh_company_task", max_retries=3)
def refresh_company_task(self, company_id: int) -> dict:
    return asyncio.run(_refresh_company(company_id))


# ── Async implementations ─────────────────────────────────────────────────────

async def _run_search(search_id: int) -> dict:
    from app.database import AsyncSessionLocal
    from app.models.search import Search
    from app.services.search_orchestrator import run_search

    async with AsyncSessionLocal() as db:
        search = await db.get(Search, search_id)
        if not search:
            return {"error": "search_not_found"}
        created = await run_search(search, db)
        await db.commit()
    return {"search_id": search_id, "companies_created": created}


async def _crawl_company(company_id: int) -> dict:
    from app.database import AsyncSessionLocal
    from app.models.company import Company
    from app.models.crawled_page import CrawledPage
    from app.models.enums import EnrichmentStatus
    from app.services.compliance_service import write_audit
    from app.services.crawler_service import crawl_website
    from app.services.extractor_service import extract_from_pages

    async with AsyncSessionLocal() as db:
        company = await db.get(Company, company_id)
        if not company or not company.website:
            return {"error": "no_website"}

        pages = await crawl_website(company.website)

        for page in pages:
            crawled = CrawledPage(
                company_id=company_id,
                url=page.url,
                status_code=page.status_code,
                title=page.title,
                text_excerpt=page.text_excerpt,
                robots_allowed=page.robots_allowed,
            )
            db.add(crawled)

        # Extract business data
        extracted = extract_from_pages(pages)
        if extracted.business_phone and not company.phone:
            company.phone = extracted.business_phone
        if extracted.business_email:
            from app.models.contact import Contact
            contact = Contact(
                company_id=company_id,
                email=extracted.business_email,
                source_url=company.website,
                source_type="company_website",
                confidence_score=0.8,
                is_personal_data=False,
            )
            db.add(contact)
        for c in extracted.contacts:
            from app.models.contact import Contact
            contact = Contact(
                company_id=company_id,
                full_name=c.full_name,
                role=c.role,
                email=c.email,
                phone=c.phone,
                source_url=c.source_url,
                source_type=c.source_type,
                confidence_score=c.confidence_score,
                is_personal_data=c.is_personal_data,
            )
            db.add(contact)

        company.enrichment_status = EnrichmentStatus.website_found
        await write_audit(db, "company", company_id, "crawled", metadata={"pages": len(pages)})
        await db.commit()

    return {"company_id": company_id, "pages_crawled": len(pages)}


async def _analyse_website(company_id: int) -> dict:
    from app.database import AsyncSessionLocal
    from app.models.company import Company
    from app.models.crawled_page import CrawledPage
    from app.models.enums import EnrichmentStatus, LeadType
    from app.services.compliance_service import evaluate_can_export, write_audit
    from app.services.scoring_service import ScoreInput, calculate_score
    from app.services.website_quality_service import analyse_website
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        company = await db.get(Company, company_id)
        if not company or not company.website:
            return {"error": "no_website"}

        result = await db.execute(
            select(CrawledPage).where(CrawledPage.company_id == company_id)
        )
        crawled_pages = result.scalars().all()

        from app.services.crawler_service import CrawlResult
        page_objects = [
            CrawlResult(p.url, p.status_code, p.title or "", p.text_excerpt or "", p.robots_allowed)
            for p in crawled_pages
        ]

        quality = await analyse_website(company.website, page_objects)
        company.has_https = quality.has_https
        company.has_mobile_viewport = quality.has_mobile_viewport
        company.has_contact_page = quality.has_contact_page
        company.website_reachable = quality.reachable
        if quality.is_weak:
            company.lead_type = LeadType.weak_website_candidate
            company.weak_website_reason = quality.summary()
        else:
            company.lead_type = LeadType.website_exists_not_target

        company.enrichment_status = EnrichmentStatus.website_analyzed

        score_input = ScoreInput(
            lead_type=company.lead_type,
            status=company.status,
            has_phone=bool(company.phone),
            has_address=bool(company.address),
            business_status_operational=True,
            industry_relevant=True,
            has_own_domain=not (company.weak_website_reason or "").startswith("no_own_website"),
            has_https=quality.has_https,
            website_reachable=quality.reachable,
            has_mobile_viewport=quality.has_mobile_viewport,
            has_contact_page=quality.has_contact_page,
            is_construction_page=quality.is_construction_page,
        )
        score, priority = calculate_score(score_input)
        company.website_opportunity_score = score
        company.lead_priority = priority

        can_export, reason = await evaluate_can_export(company, db)
        company.can_export = can_export
        company.export_block_reason = reason

        await write_audit(db, "company", company_id, "website_analysed",
                          metadata={"score": score, "weak": quality.is_weak})
        await db.commit()

    return {"company_id": company_id, "score": score, "is_weak": quality.is_weak}


async def _refresh_company(company_id: int) -> dict:
    from app.database import AsyncSessionLocal
    from app.models.company import Company
    from app.services.compliance_service import evaluate_can_export, write_audit
    from app.services.places_service import refresh_place
    from app.services.website_detection_service import classify_from_place, normalize_domain
    from app.services.dedupe_service import normalize_phone
    from app.services.scoring_service import ScoreInput, calculate_score

    async with AsyncSessionLocal() as db:
        company = await db.get(Company, company_id)
        if not company or not company.google_place_id:
            return {"error": "no_place_id"}

        place = await refresh_place(company.google_place_id)
        if not place:
            return {"error": "place_not_found"}

        lead_type, enrichment_status, weak_reason = classify_from_place(place)
        company.website = place.website_uri
        company.normalized_domain = normalize_domain(place.website_uri)
        company.website_available = place.has_website
        company.phone = normalize_phone(place.phone) or company.phone
        company.lead_type = lead_type
        company.enrichment_status = enrichment_status
        company.weak_website_reason = weak_reason
        company.google_data_expires_at = place.expires_at

        score_input = ScoreInput(
            lead_type=lead_type,
            status=company.status,
            has_phone=bool(place.phone),
            has_address=bool(place.formatted_address),
            business_status_operational=(place.business_status == "OPERATIONAL"),
            industry_relevant=True,
        )
        score, priority = calculate_score(score_input)
        company.website_opportunity_score = score
        company.lead_priority = priority

        can_export, reason = await evaluate_can_export(company, db)
        company.can_export = can_export
        company.export_block_reason = reason

        await write_audit(db, "company", company_id, "refreshed_from_google")
        await db.commit()

    return {"company_id": company_id, "lead_type": lead_type.value, "score": score}
