from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.search import Search
from app.schemas.search import SearchCreate, SearchOut
from app.workers.tasks import run_search_task

router = APIRouter()


def _dispatch_search(search_id: int) -> None:
    """Fire-and-forget Celery dispatch (runs in BackgroundTask after response sent)."""
    run_search_task.delay(search_id)


@router.post("/search", response_model=SearchOut, status_code=202)
async def create_search(
    payload: SearchCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> Search:
    search = Search(
        industry=payload.industry,
        location=payload.location,
        radius_km=payload.radius_km,
        keywords=payload.keywords,
        target=payload.target,
        max_results=payload.max_results,
        status="queued",
    )
    db.add(search)
    await db.flush()
    await db.commit()
    await db.refresh(search)

    # Dispatch after response is sent so the client isn't blocked by Redis latency
    background_tasks.add_task(_dispatch_search, search.id)

    return search


@router.get("/searches", response_model=list[SearchOut])
async def list_searches(
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
) -> list[Search]:
    result = await db.execute(
        select(Search).order_by(Search.created_at.desc()).limit(limit).offset(offset)
    )
    return list(result.scalars().all())


@router.get("/searches/{search_id}", response_model=SearchOut)
async def get_search(search_id: int, db: AsyncSession = Depends(get_db)) -> Search:
    search = await db.get(Search, search_id)
    if not search:
        raise HTTPException(status_code=404, detail="Search not found")
    return search
