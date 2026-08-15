"""
ScrapeGraphAI integration — LLM-driven scraping graphs.

Complements the deterministic scrapers (Scrapy spider, Playwright client):
instead of hand-written selectors, a natural-language prompt plus a Pydantic
schema drive the extraction, so a layout change does not break the pipeline.

Two deliberate constraints:
  - The ``scrapegraphai`` import is deferred to call time. It pulls a large
    dependency tree, so every other module must stay importable without it.
  - robots.txt is honoured before a graph fetches a URL, matching the policy of
    the crawler in ``app/services/crawler_service.py``.

Graphs are synchronous and blocking, so every entry point builds and runs its
graph in a worker thread via ``asyncio.to_thread``.
"""

from __future__ import annotations

import asyncio
from types import ModuleType
from typing import Any, TypeVar
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx
import structlog
from pydantic import BaseModel, Field

from app.core.config import settings

log = structlog.get_logger()

ROBOTS_USER_AGENT = "LeadScraperBot"

DEFAULT_LEAD_PROMPT = (
    "Extract the business contact details of the company this website belongs to. "
    "Only return information that is explicitly printed on the page. "
    "Never guess an email address, a phone number or a person's name — "
    "leave a field null when the page does not state it."
)

DEFAULT_SEARCH_PROMPT = (
    "Find businesses matching the request and return their contact details. "
    "Only return details that are explicitly stated on the pages you read."
)

_ModelT = TypeVar("_ModelT", bound=BaseModel)


class ScrapeGraphUnavailableError(RuntimeError):
    """Raised when the optional ``scrapegraphai`` dependency is not installed."""


class RobotsDisallowedError(RuntimeError):
    """Raised when robots.txt forbids fetching the requested URL."""


class ScrapedLead(BaseModel):
    """Output schema handed to the graph — mirrors the columns of ``models.lead.Lead``."""

    company_name: str | None = Field(None, description="Official company or business name")
    email: str | None = Field(None, description="Contact email, only if printed on the page")
    phone: str | None = Field(None, description="Contact phone number as printed")
    address: str | None = Field(None, description="Full physical address")
    city: str | None = Field(None, description="City")
    country: str | None = Field(None, description="Country")
    description: str | None = Field(None, description="One-sentence company description")
    industry: str | None = Field(None, description="Industry / sector")
    social_links: list[str] = Field(
        default_factory=list, description="Social media profile URLs linked on the page"
    )


class ScrapedLeadBatch(BaseModel):
    """Output schema for the multi-page and search graphs."""

    leads: list[ScrapedLead] = Field(default_factory=list)


class SearchResult(BaseModel):
    leads: list[ScrapedLead] = Field(default_factory=list)
    considered_urls: list[str] = Field(default_factory=list)


def _graphs() -> ModuleType:
    """Import ``scrapegraphai.graphs`` lazily, with an actionable error if it is missing."""

    try:
        from scrapegraphai import graphs
    except ImportError as exc:
        raise ScrapeGraphUnavailableError(
            "scrapegraphai is not installed — install it with: "
            "pip install 'scrapegraphai>=1.76.0,<2.0.0'"
        ) from exc
    return graphs


def _qualified_model(model: str) -> str:
    """ScrapeGraphAI resolves the provider from a ``provider/model`` string."""

    return model if "/" in model else f"openai/{model}"


def build_graph_config(**overrides: Any) -> dict[str, Any]:
    """
    Build the graph config from settings.

    ``overrides`` replaces top-level keys; an ``llm`` override is merged into the
    configured LLM block rather than replacing it.
    """

    config: dict[str, Any] = {
        "llm": {
            "api_key": settings.openai_api_key,
            "model": _qualified_model(settings.scrapegraph_model),
            "temperature": 0,
        },
        "verbose": settings.scrapegraph_verbose,
        "headless": settings.scrapegraph_headless,
        "timeout": settings.scrapegraph_timeout,
    }
    llm_overrides = overrides.pop("llm", None)
    if llm_overrides:
        config["llm"] = {**config["llm"], **llm_overrides}
    config.update(overrides)
    return config


def _coerce(model: type[_ModelT], raw: Any) -> _ModelT:
    """Graphs return a dict shaped like the schema, but fall back to prose on failure."""

    if isinstance(raw, model):
        return raw
    if isinstance(raw, BaseModel):
        return model.model_validate(raw.model_dump())
    if isinstance(raw, dict):
        return model.model_validate(raw)
    raise ValueError(f"ScrapeGraphAI returned no structured answer: {raw!r}")


async def robots_allow(url: str) -> bool:
    """Check robots.txt for ``url``. Fails open — an unreachable robots.txt is not a ban."""

    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    parser = RobotFileParser()
    parser.set_url(robots_url)
    try:
        async with httpx.AsyncClient(timeout=5, follow_redirects=True) as client:
            response = await client.get(robots_url, headers={"User-Agent": ROBOTS_USER_AGENT})
        if response.status_code == 200:
            parser.parse(response.text.splitlines())
    except httpx.HTTPError as exc:
        log.warning("robots_fetch_failed", url=robots_url, error=str(exc))
        return True

    try:
        return parser.can_fetch(ROBOTS_USER_AGENT, url)
    except Exception:
        return True


async def _ensure_crawlable(url: str) -> None:
    if not settings.scrapegraph_respect_robots:
        return
    if not await robots_allow(url):
        log.info("robots_disallowed", url=url, source="scrapegraphai")
        raise RobotsDisallowedError(f"robots.txt disallows fetching {url}")


def _run_graph(graph_name: str, **kwargs: Any) -> Any:
    """Instantiate and run a graph. Blocking — always called via ``asyncio.to_thread``."""

    graph_cls = getattr(_graphs(), graph_name)
    return graph_cls(**kwargs).run()


async def scrape_lead(
    url: str, prompt: str = DEFAULT_LEAD_PROMPT, **config_overrides: Any
) -> ScrapedLead:
    """Extract a single lead from a live URL via ``SmartScraperGraph``."""

    await _ensure_crawlable(url)
    raw = await asyncio.to_thread(
        _run_graph,
        "SmartScraperGraph",
        prompt=prompt,
        source=url,
        config=build_graph_config(**config_overrides),
        schema=ScrapedLead,
    )
    log.info("scrapegraph_scrape_done", url=url)
    return _coerce(ScrapedLead, raw)


async def scrape_lead_from_html(
    html: str, url: str, prompt: str = DEFAULT_LEAD_PROMPT, **config_overrides: Any
) -> ScrapedLead:
    """
    Extract a lead from already-fetched HTML.

    Bridges the Playwright client into ScrapeGraphAI: the page is fetched once by
    the browser (cookie banners, JS rendering) and only the markup is handed to
    the graph, so no second request hits the site.
    """

    raw = await asyncio.to_thread(
        _run_graph,
        "SmartScraperGraph",
        prompt=prompt,
        source=html,
        config=build_graph_config(**config_overrides),
        schema=ScrapedLead,
    )
    log.info("scrapegraph_html_scrape_done", url=url)
    return _coerce(ScrapedLead, raw)


async def scrape_leads(
    urls: list[str], prompt: str = DEFAULT_LEAD_PROMPT, **config_overrides: Any
) -> ScrapedLeadBatch:
    """Extract leads from several URLs in one run via ``SmartScraperMultiGraph``."""

    allowed = [u for u in urls if not settings.scrapegraph_respect_robots or await robots_allow(u)]
    skipped = len(urls) - len(allowed)
    if skipped:
        log.info("robots_disallowed_skipped", count=skipped, source="scrapegraphai")
    if not allowed:
        raise RobotsDisallowedError("robots.txt disallows fetching every requested URL")

    raw = await asyncio.to_thread(
        _run_graph,
        "SmartScraperMultiGraph",
        prompt=prompt,
        source=allowed,
        config=build_graph_config(**config_overrides),
        schema=ScrapedLeadBatch,
    )
    log.info("scrapegraph_multi_scrape_done", urls=len(allowed))
    return _coerce(ScrapedLeadBatch, raw)


async def search_leads(
    query: str,
    max_results: int | None = None,
    prompt: str = DEFAULT_SEARCH_PROMPT,
    **config_overrides: Any,
) -> SearchResult:
    """
    Search the web for matching businesses via ``SearchGraph``.

    The graph picks the source URLs itself, so it is exposed for research —
    persist a lead from it only after the source URL has been reviewed.
    """

    config = build_graph_config(
        max_results=max_results or settings.scrapegraph_max_results, **config_overrides
    )
    graph_cls = _graphs().SearchGraph
    graph = await asyncio.to_thread(
        graph_cls, prompt=f"{prompt}\n\nRequest: {query}", config=config, schema=ScrapedLeadBatch
    )
    raw = await asyncio.to_thread(graph.run)
    batch = _coerce(ScrapedLeadBatch, raw)
    considered = list(graph.get_considered_urls())
    log.info("scrapegraph_search_done", query=query, urls=len(considered))
    return SearchResult(leads=batch.leads, considered_urls=considered)
