"""
Analyses crawled pages to determine website quality.
Only uses data fetched from the public website — no third-party APIs.
"""

from __future__ import annotations

import re
import time
from datetime import datetime
from urllib.parse import urlparse

import httpx
import structlog
from bs4 import BeautifulSoup

from app.config import settings
from app.services.crawler_service import CrawlResult

log = structlog.get_logger()

_CONTACT_KEYWORDS = re.compile(
    r"kontakt|contact|telefon|phone|e-mail|email|impressum|anruf|reach", re.I
)
_CONSTRUCTION_PATTERNS = re.compile(
    r"coming soon|under construction|demnächst|in kürze|baustelle|work in progress", re.I
)
_OLD_COPYRIGHT = re.compile(r"©\s*(199\d|200[0-9]|201[0-5])")


class WebsiteQualityResult:
    def __init__(self) -> None:
        self.reachable: bool = False
        self.has_https: bool = False
        self.has_mobile_viewport: bool = False
        self.has_contact_info: bool = False
        self.has_contact_page: bool = False
        self.is_construction_page: bool = False
        self.has_old_copyright: bool = False
        self.load_time_ms: int | None = None
        self.http_error: bool = False
        self.is_social_redirect: bool = False
        self.reasons: list[str] = []

    @property
    def weakness_count(self) -> int:
        return len(self.reasons)

    @property
    def is_weak(self) -> bool:
        return self.weakness_count >= 2

    def summary(self) -> str:
        return "; ".join(self.reasons) if self.reasons else "ok"


async def analyse_website(url: str, crawled_pages: list[CrawlResult]) -> WebsiteQualityResult:
    result = WebsiteQualityResult()

    # HTTPS check
    result.has_https = url.startswith("https://")
    if not result.has_https:
        result.reasons.append("no_https")

    # Reachability + load time
    start = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=settings.crawler_timeout_seconds, follow_redirects=True) as client:
            resp = await client.head(url)
            result.load_time_ms = int((time.monotonic() - start) * 1000)
            result.reachable = resp.status_code < 400
            if not result.reachable:
                result.http_error = True
                result.reasons.append(f"http_error_{resp.status_code}")
    except Exception:
        result.http_error = True
        result.reasons.append("unreachable")

    if result.load_time_ms and result.load_time_ms > 5000:
        result.reasons.append("slow_load")

    # Analyse crawled page content
    allowed_pages = [p for p in crawled_pages if p.robots_allowed and p.status_code == 200]

    if not allowed_pages:
        result.reasons.append("no_crawlable_content")
        return result

    all_text = " ".join(p.text_excerpt for p in allowed_pages)
    first_page_html = allowed_pages[0].text_excerpt if allowed_pages else ""

    # Mobile viewport — check title/text for meta viewport hint
    # (Full HTML not stored; we check via a quick re-fetch of the homepage)
    homepage_page = next((p for p in allowed_pages if _is_homepage(p.url)), allowed_pages[0])
    result.has_mobile_viewport = await _check_viewport(url)
    if not result.has_mobile_viewport:
        result.reasons.append("no_mobile_viewport")

    # Contact signals
    result.has_contact_info = bool(_CONTACT_KEYWORDS.search(all_text))
    result.has_contact_page = any(
        "kontakt" in p.url.lower() or "contact" in p.url.lower() or "impressum" in p.url.lower()
        for p in allowed_pages
    )
    if not result.has_contact_info:
        result.reasons.append("no_contact_info")
    if not result.has_contact_page:
        result.reasons.append("no_contact_page")

    # Construction page
    if _CONSTRUCTION_PATTERNS.search(all_text):
        result.is_construction_page = True
        result.reasons.append("construction_page")

    # Old copyright
    if _OLD_COPYRIGHT.search(all_text):
        result.has_old_copyright = True
        result.reasons.append("old_copyright")

    return result


async def _check_viewport(url: str) -> bool:
    try:
        async with httpx.AsyncClient(timeout=5, follow_redirects=True) as client:
            resp = await client.get(url, headers={"User-Agent": settings.crawler_user_agent})
            return 'name="viewport"' in resp.text.lower()
    except Exception:
        return False


def _is_homepage(url: str) -> bool:
    path = urlparse(url).path
    return path in ("", "/")
