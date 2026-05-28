from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file="../.env", extra="ignore")

    # App
    app_name: str = "Autonomous Lead Scraper"
    debug: bool = False
    log_level: str = "INFO"
    secret_key: str = Field(..., min_length=16)

    # Database
    database_url: str = "postgresql+asyncpg://postgres:password@localhost:5432/lead_scraper"
    redis_url: str = "redis://localhost:6379/0"

    # OpenAI
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    # Google Maps
    google_maps_api_key: str = ""

    # HubSpot
    hubspot_access_token: str = ""

    # Pipedrive
    pipedrive_api_key: str = ""
    pipedrive_company_domain: str = ""

    # Salesforce
    salesforce_username: str = ""
    salesforce_password: str = ""
    salesforce_security_token: str = ""
    salesforce_domain: str = "login"

    # Temporal
    temporal_host: str = "localhost:7233"
    temporal_namespace: str = "default"

    # Celery
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"


settings = Settings()
