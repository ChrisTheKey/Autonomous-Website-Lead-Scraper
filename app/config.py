from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    debug: bool = False

    database_url: str = "postgresql+asyncpg://postgres:password@localhost:5432/lead_discovery"
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    google_maps_api_key: str = ""
    # Google Places API (New) endpoint
    google_places_base_url: str = "https://places.googleapis.com/v1"

    max_results_per_search: int = Field(100, ge=1, le=500)
    max_pages_per_domain: int = Field(10, ge=1, le=50)
    google_data_ttl_days: int = Field(30, ge=1, le=365)
    export_requires_verification: bool = True

    # Crawler
    crawler_timeout_seconds: int = 10
    crawler_user_agent: str = (
        "LeadDiscoveryBot/1.0 (commercial lead tool; respects robots.txt)"
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
