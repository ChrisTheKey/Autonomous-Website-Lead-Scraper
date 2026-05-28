from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, HttpUrl

from app.tasks.scrape_tasks import run_scrape_task

router = APIRouter()


class ScrapeRequest(BaseModel):
    url: HttpUrl
    use_browser: bool = False
    depth: int = 1


class ScrapeResponse(BaseModel):
    task_id: str
    status: str


@router.post("/", response_model=ScrapeResponse)
async def start_scrape(
    payload: ScrapeRequest,
    background_tasks: BackgroundTasks,
) -> ScrapeResponse:
    task = run_scrape_task.delay(str(payload.url), payload.use_browser, payload.depth)
    return ScrapeResponse(task_id=task.id, status="queued")


@router.get("/{task_id}")
async def scrape_status(task_id: str) -> dict:
    from app.tasks.scrape_tasks import celery_app

    result = celery_app.AsyncResult(task_id)
    if result.state == "FAILURE":
        raise HTTPException(status_code=500, detail=str(result.result))
    return {"task_id": task_id, "state": result.state, "result": result.result}
