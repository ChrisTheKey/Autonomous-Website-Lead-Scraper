from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "lead_scraper",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "app.tasks.scrape_tasks",
        "app.tasks.enrich_tasks",
        "app.tasks.crm_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    worker_prefetch_multiplier=1,
    task_routes={
        "app.tasks.scrape_tasks.*": {"queue": "scrape"},
        "app.tasks.enrich_tasks.*": {"queue": "enrich"},
        "app.tasks.crm_tasks.*": {"queue": "crm"},
    },
)
