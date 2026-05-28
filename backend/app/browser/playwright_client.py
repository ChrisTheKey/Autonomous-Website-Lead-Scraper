import asyncio
import re
from dataclasses import dataclass

import structlog
from playwright.async_api import Browser, Page, async_playwright

log = structlog.get_logger()


@dataclass
class BrowserResult:
    url: str
    html: str
    title: str
    emails: list[str]
    phones: list[str]
    screenshot_b64: str | None = None


async def scrape_with_browser(
    url: str,
    *,
    take_screenshot: bool = False,
    wait_for: str = "networkidle",
    timeout_ms: int = 30_000,
) -> BrowserResult:
    async with async_playwright() as pw:
        browser: Browser = await pw.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        page: Page = await browser.new_page(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 Chrome/124.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
        )
        try:
            await page.goto(url, wait_until=wait_for, timeout=timeout_ms)
            html = await page.content()
            title = await page.title()
            emails = _extract_emails(html)
            phones = _extract_phones(html)
            screenshot_b64 = None
            if take_screenshot:
                import base64
                buf = await page.screenshot(full_page=True)
                screenshot_b64 = base64.b64encode(buf).decode()
            return BrowserResult(
                url=url,
                html=html,
                title=title,
                emails=emails,
                phones=phones,
                screenshot_b64=screenshot_b64,
            )
        finally:
            await browser.close()


async def scrape_multiple(urls: list[str], concurrency: int = 3) -> list[BrowserResult]:
    sem = asyncio.Semaphore(concurrency)

    async def _bounded(u: str) -> BrowserResult:
        async with sem:
            try:
                return await scrape_with_browser(u)
            except Exception as exc:
                log.warning("browser_scrape_failed", url=u, error=str(exc))
                return BrowserResult(url=u, html="", title="", emails=[], phones=[])

    return await asyncio.gather(*[_bounded(u) for u in urls])


def _extract_emails(text: str) -> list[str]:
    return list(set(re.findall(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", text)))


def _extract_phones(text: str) -> list[str]:
    raw = re.findall(r"(\+?[\d\s\-().]{7,20})", text)
    return list(set(p.strip() for p in raw if len(re.sub(r"\D", "", p)) >= 7))
