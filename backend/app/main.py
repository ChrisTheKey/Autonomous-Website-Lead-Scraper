from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import ai_extract, crm, google_maps, leads, scrapegraph, scraper
from app.core.config import settings

log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("startup", app=settings.app_name)
    yield
    log.info("shutdown")


app = FastAPI(
    title=settings.app_name,
    description="Autonomous lead scraper with AI extraction and CRM sync",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(leads.router, prefix="/api/leads", tags=["leads"])
app.include_router(scraper.router, prefix="/api/scraper", tags=["scraper"])
app.include_router(ai_extract.router, prefix="/api/ai", tags=["ai"])
app.include_router(scrapegraph.router, prefix="/api/scrapegraph", tags=["scrapegraph"])
app.include_router(google_maps.router, prefix="/api/maps", tags=["maps"])
app.include_router(crm.router, prefix="/api/crm", tags=["crm"])


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
