"""
Scrapling-based web scraper — wraps D4Vinci/Scrapling for targeted contact extraction.

Advantages over plain httpx + BeautifulSoup:
  - Auto-adapts CSS/XPath selectors across site changes
  - Built-in anti-bot bypass via curl_cffi (stealth TLS fingerprint)
  - Smart mailto: and tel: link detection
  - Cleaner text extraction (strips nav/footer/ads automatically)
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from typing import Optional

import structlog

log = structlog.get_logger()

SKIP_DOMAINS = {
    "facebook.com", "instagram.com", "twitter.com", "x.com",
    "linkedin.com", "tiktok.com", "youtube.com", "google.com",
    "local.ch", "search.ch", "yellow.ch", "tripadvisor.com",
}

CONTACT_PATHS = [
    "/kontakt", "/contact", "/impressum", "/imprint",
    "/ueber-uns", "/ueber-mich", "/about", "/about-us",
    "/team", "/wir",
]

EMAIL_SKIP = {"noreply", "no-reply", "example", "test@", "@test",
              "sentry", "placeholder", "yourname", "name@", "@domain"}

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")


@dataclass
class ScraplingResult:
    email: str = ""
    phone: str = ""
    page_text: str = ""
    source_url: str = ""
    success: bool = False


def _extract_email_from_text(text: str) -> str:
    for m in EMAIL_RE.findall(text):
        if not any(s in m.lower() for s in EMAIL_SKIP):
            return m
    return ""


def _parse_page(html: str, url: str) -> ScraplingResult:
    """
    Parse a single HTML page with Scrapling's Adaptor.
    Falls back to regex if Scrapling is unavailable.
    """
    try:
        from scrapling.parser import Adaptor

        page = Adaptor(html, url=url)

        # --- Email: prefer mailto: links (most reliable) ---
        email = ""
        for a in page.css("a[href^='mailto:']"):
            href = a.attrib.get("href", "")
            addr = href.replace("mailto:", "").split("?")[0].strip()
            if addr and not any(s in addr.lower() for s in EMAIL_SKIP):
                email = addr
                break

        # Fallback: scan visible text for email pattern
        if not email:
            full_text = "\n".join(page.xpath("//text()").getall())
            email = _extract_email_from_text(full_text)

        # --- Phone: tel: links ---
        phone = ""
        for a in page.css("a[href^='tel:']"):
            href = a.attrib.get("href", "")
            phone = href.replace("tel:", "").strip()
            if phone:
                break

        # --- Clean text for Claude ---
        # Remove noisy containers
        for sel in ("script", "style", "nav", "footer", "head", "iframe"):
            for el in page.css(sel):
                pass  # Adaptor is read-only; we'll strip via xpath filter

        # Grab body text via xpath (skips script/style automatically in most parsers)
        try:
            raw_lines = page.xpath(
                "//body//*[not(self::script or self::style or self::nav or self::footer)]"
                "//text()"
            ).getall()
        except Exception:
            raw_lines = page.xpath("//text()").getall()

        lines = [l.strip() for l in raw_lines if l.strip()]
        page_text = "\n".join(lines[:300])

        return ScraplingResult(
            email=email,
            phone=phone,
            page_text=page_text,
            source_url=url,
            success=True,
        )

    except ImportError:
        # Scrapling not installed — fall back to regex on raw HTML
        log.warning("scrapling_not_available", fallback="regex")
        text = re.sub(r"<[^>]+>", " ", html)
        text = re.sub(r"\s+", " ", text)[:8000]
        return ScraplingResult(
            email=_extract_email_from_text(text),
            page_text=text,
            source_url=url,
            success=False,
        )

    except Exception as e:
        log.debug("scrapling_parse_error", url=url, error=str(e))
        return ScraplingResult(source_url=url)


async def _fetch_html(url: str, use_stealth: bool = False) -> str:
    """
    Fetch raw HTML. Tries Scrapling's AsyncFetcher first, falls back to httpx.
    use_stealth=True uses curl_cffi for anti-bot bypass (slower).
    """
    # --- Scrapling AsyncFetcher ---
    try:
        if use_stealth:
            from scrapling import StealthyFetcher
            # StealthyFetcher is sync; run in thread
            loop = asyncio.get_event_loop()
            page = await loop.run_in_executor(
                None, lambda: StealthyFetcher.fetch(url, timeout=15)
            )
            return page.html_content if page else ""
        else:
            from scrapling import AsyncFetcher
            page = await AsyncFetcher.fetch(url, timeout=15)
            return page.html_content if page else ""
    except Exception:
        pass

    # --- httpx fallback ---
    try:
        import httpx, ssl
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        async with httpx.AsyncClient(
            verify=False,
            follow_redirects=True,
            timeout=12,
            headers={"User-Agent": "Mozilla/5.0 (compatible; LeadBot/1.0)"},
        ) as client:
            r = await client.get(url, timeout=12)
            return r.text[:80_000]
    except Exception as e:
        log.debug("scrapling_fetch_fallback_failed", url=url, error=str(e))
        return ""


async def scrape_contact_pages(
    base_url: str,
    max_pages: int = 5,
    use_stealth: bool = False,
) -> tuple[str, str, str]:
    """
    Scrapes contact-relevant pages from a website.

    Returns: (email, phone, combined_text)
    combined_text is ready to pass to Claude for name extraction.
    """
    if not base_url:
        return "", "", ""

    try:
        from urllib.parse import urlparse
        domain = urlparse(base_url.lower()).netloc.lstrip("www.")
        if any(domain == s or domain.endswith("." + s) for s in SKIP_DOMAINS):
            return "", "", base_url
    except Exception:
        pass

    base = base_url.rstrip("/")
    pages = [base] + [base + p for p in CONTACT_PATHS]

    email = phone = ""
    combined_text = ""
    fetched = 0

    for page_url in pages[:max_pages]:
        html = await _fetch_html(page_url, use_stealth=use_stealth)
        if not html:
            continue

        result = _parse_page(html, page_url)
        fetched += 1

        if not email and result.email:
            email = result.email
        if not phone and result.phone:
            phone = result.phone

        combined_text += "\n" + result.page_text

        await asyncio.sleep(0.3)

        # Early exit once we have enough material
        if email and len(combined_text) > 3000:
            break

    log.debug("scrapling_done", url=base_url, pages=fetched, has_email=bool(email))
    return email, phone, combined_text[:8000]
