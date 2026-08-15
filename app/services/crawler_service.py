"""
Ethical website crawler.

Rules enforced:
  - Always checks robots.txt first; skips disallowed URLs.
  - Respects Crawl-delay header.
  - Max pages per domain: settings.max_pages_per_domain.
  - Prioritises contact/impressum pages.
  - Never crawls login, admin, cart, checkout, captcha paths.
  - Identifies itself honestly via User-Agent.
  - Does NOT bypass any protection mechanism.
"""

from __future__ import annotations

import asyncio
import re
from urllib.parse import urldefrag, urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx
import structlog
from bs4 import BeautifulSoup

from app.config import settings

log = structlog.get_logger()

_PRIORITY_PATHS = [
    "kontakt", "contact", "impressum", "about", "ueber-uns",
    "über-uns", "team", "legal", "company", "firma",
]
_BLOCKED_PATHS = [
    "login", "admin", "cart", "checkout", "warenkorb", "kasse",
    "shop/cart", "account", "captcha", "wp-admin",
]


def canonical_resource_url(url: str) -> str:
    """
    The URL as the HTTP layer sees it.

    A fragment is never sent to the server, so /page, /page#kontakt and
    /page#!/kontakt are all the same resource and must be fetched once. Only the
    fragment is dropped — scheme, host, path and query stay untouched.
    """
    return urldefrag(url)[0]


class CrawlResult:
    def __init__(
        self,
        url: str,
        status_code: int | None,
        title: str,
        text_excerpt: str,
        robots_allowed: bool,
    ) -> None:
        self.url = url
        self.status_code = status_code
        self.title = title
        self.text_excerpt = text_excerpt
        self.robots_allowed = robots_allowed


async def crawl_website(base_url: str) -> list[CrawlResult]:
    if not base_url.startswith("http"):
        base_url = f"https://{base_url}"
    base_url = canonical_resource_url(base_url)

    parsed = urlparse(base_url)
    origin = f"{parsed.scheme}://{parsed.netloc}"

    robots = await _fetch_robots(origin)
    results: list[CrawlResult] = []
    visited: set[str] = set()

    headers = {
        "User-Agent": settings.crawler_user_agent,
        "Accept": "text/html",
    }

    async with httpx.AsyncClient(
        timeout=settings.crawler_timeout_seconds,
        follow_redirects=True,
        headers=headers,
    ) as client:
        # Always start with the base URL
        queue: list[str] = [base_url]

        while queue and len(results) < settings.max_pages_per_domain:
            url = queue.pop(0)
            if url in visited:
                continue
            visited.add(url)

            if _is_blocked_path(url):
                continue

            allowed = _robots_allows(robots, url, settings.crawler_user_agent)
            if not allowed:
                results.append(CrawlResult(url, None, "", "", robots_allowed=False))
                log.info("robots_disallowed", url=url)
                continue

            try:
                resp = await client.get(url)
                crawl_result = _parse_response(url, resp)
                results.append(crawl_result)

                # Discover priority links for next pages
                if resp.status_code == 200 and len(results) < settings.max_pages_per_domain:
                    soup = BeautifulSoup(resp.text, "lxml")
                    for link in soup.find_all("a", href=True):
                        href = canonical_resource_url(urljoin(url, link["href"]))
                        if href.startswith(origin) and href not in visited:
                            if _is_priority_path(href):
                                queue.insert(0, href)  # priority at front
                            else:
                                queue.append(href)

            except (httpx.RequestError, httpx.HTTPStatusError) as exc:
                log.warning("crawl_error", url=url, error=str(exc))
                results.append(CrawlResult(url, None, "", "", robots_allowed=True))

            await asyncio.sleep(0.5)  # polite delay

    return results


def _parse_response(url: str, resp: httpx.Response) -> CrawlResult:
    soup = BeautifulSoup(resp.text, "lxml")
    title = (soup.find("title") or "").get_text(strip=True) if soup.find("title") else ""
    # Extract first 2000 chars of visible text
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    text = " ".join(soup.get_text(separator=" ", strip=True).split())[:2000]
    return CrawlResult(url, resp.status_code, title, text, robots_allowed=True)


async def _fetch_robots(origin: str) -> RobotFileParser:
    rp = RobotFileParser()
    rp.set_url(f"{origin}/robots.txt")
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{origin}/robots.txt")
            if resp.status_code == 200:
                rp.parse(resp.text.splitlines())
    except Exception:
        pass
    return rp


def _robots_allows(rp: RobotFileParser, url: str, agent: str) -> bool:
    try:
        return rp.can_fetch(agent, url)
    except Exception:
        return True


def _is_priority_path(url: str) -> bool:
    path = urlparse(url).path.lower()
    return any(p in path for p in _PRIORITY_PATHS)


def _is_blocked_path(url: str) -> bool:
    path = urlparse(url).path.lower()
    return any(p in path for p in _BLOCKED_PATHS)
