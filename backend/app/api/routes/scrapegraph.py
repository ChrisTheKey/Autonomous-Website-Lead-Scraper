from collections.abc import Iterator
from contextlib import contextmanager

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, HttpUrl

from app.ai.scrapegraph_client import (
    DEFAULT_LEAD_PROMPT,
    DEFAULT_SEARCH_PROMPT,
    RobotsDisallowedError,
    ScrapedLead,
    ScrapedLeadBatch,
    ScrapeGraphUnavailableError,
    SearchResult,
    scrape_lead,
    scrape_leads,
    search_leads,
)
from app.tasks.scrape_tasks import run_scrapegraph_task

router = APIRouter()


class GraphScrapeRequest(BaseModel):
    url: HttpUrl
    prompt: str = DEFAULT_LEAD_PROMPT


class GraphScrapeManyRequest(BaseModel):
    urls: list[HttpUrl] = Field(min_length=1, max_length=20)
    prompt: str = DEFAULT_LEAD_PROMPT


class GraphSearchRequest(BaseModel):
    query: str = Field(min_length=3)
    max_results: int | None = Field(None, ge=1, le=20)
    prompt: str = DEFAULT_SEARCH_PROMPT


class TaskResponse(BaseModel):
    task_id: str
    status: str


@contextmanager
def _graph_errors() -> Iterator[None]:
    """Translate the wrapper's failure modes into HTTP responses."""

    try:
        yield
    except RobotsDisallowedError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ScrapeGraphUnavailableError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/scrape", response_model=ScrapedLead)
async def scrape(payload: GraphScrapeRequest) -> ScrapedLead:
    with _graph_errors():
        return await scrape_lead(str(payload.url), payload.prompt)


@router.post("/scrape-many", response_model=ScrapedLeadBatch)
async def scrape_many(payload: GraphScrapeManyRequest) -> ScrapedLeadBatch:
    with _graph_errors():
        return await scrape_leads([str(u) for u in payload.urls], payload.prompt)


@router.post("/search", response_model=SearchResult)
async def search(payload: GraphSearchRequest) -> SearchResult:
    with _graph_errors():
        return await search_leads(payload.query, payload.max_results, payload.prompt)


@router.post("/tasks", response_model=TaskResponse)
async def enqueue_scrape(payload: GraphScrapeRequest) -> TaskResponse:
    """Scrape in the background and persist the result as a lead."""

    task = run_scrapegraph_task.delay(str(payload.url), payload.prompt)
    return TaskResponse(task_id=task.id, status="queued")
