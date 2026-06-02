# Autonomous Website Lead Scraper — Claude Code Guide

## Project Overview

FastAPI-based B2B lead discovery service that finds local businesses without websites using the Google Places API. Stores leads in PostgreSQL, processes them via Celery/Redis, and integrates with Claude AI for lead scoring.

## Architecture

```
app/
  api/           # FastAPI routers
  models/        # SQLAlchemy ORM models
  services/      # Business logic (AI, CRM, crawling, webhooks, email)
  workers/       # Celery tasks
  config.py      # Pydantic settings (reads from .env)
  database.py    # Async SQLAlchemy session factory
  main.py        # FastAPI app + router registration
backend/
  dashboard.py   # Streamlit dashboard
```

## Development Commands

```bash
# Start all services
docker compose up -d

# API only (dev)
uvicorn app.main:app --reload

# Run Celery worker
celery -A app.workers.celery_app worker --loglevel=info

# Database migrations
alembic upgrade head

# Run tests
pytest

# Streamlit dashboard
streamlit run backend/dashboard.py
```

## Environment Variables

Copy `.env.example` to `.env` and fill in:

```
DATABASE_URL=postgresql+asyncpg://...
REDIS_URL=redis://localhost:6379/0
GOOGLE_MAPS_API_KEY=...
ANTHROPIC_API_KEY=...        # Required for AI analysis
HUBSPOT_API_KEY=...          # Optional: CRM sync
SALESFORCE_USERNAME=...      # Optional: CRM sync
PIPEDRIVE_API_TOKEN=...      # Optional: CRM sync
WEBHOOK_SECRET=...           # Optional: HMAC signing for webhooks
```

## Claude API Usage

This project uses `claude-opus-4-8` via the Anthropic Python SDK (`anthropic>=0.50.0`).

### Model

```python
from app.config import settings
# settings.claude_model == "claude-opus-4-8"
```

### AI Service (`app/services/ai_service.py`)

```python
from app.services.ai_service import analyse_company

analysis = await analyse_company(
    company_name="Muster GmbH",
    industry="Coiffeur",
    location="Zürich",
    website=None,
    phone="+41 44 123 45 67",
)
# analysis.opportunity_score: int (0–100)
# analysis.opportunity_summary: str
# analysis.recommended_action: str
# analysis.confidence: float
```

The service uses **adaptive thinking** (`thinking={"type": "adaptive"}`) and streaming, as required by `claude-opus-4-8`.

### Migrating to a newer Claude model

Run `/claude-api migrate` in Claude Code and follow the prompts. The target branch for changes is `claude/trusting-cannon-IHn6a`.

When migrating:
1. Update `CLAUDE_MODEL` in `.env` / `.env.example`
2. Update `claude_model` default in `app/config.py`
3. Check `app/services/ai_service.py` — `thinking={"type": "adaptive"}` works for all Opus 4.x models
4. Run `pytest` to verify nothing broke

## Key API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/search` | Trigger a new Google Places search |
| GET | `/companies` | List companies with filters |
| POST | `/companies/{id}/verify` | Mark company verified |
| POST | `/companies/{id}/ai-analyse` | Run Claude AI analysis |
| POST | `/companies/{id}/crm-push` | Push to HubSpot/Salesforce/Pipedrive |
| POST | `/companies/{id}/validate-email` | DNS MX email validation |
| POST | `/batch/verify` | Bulk verify |
| POST | `/batch/ai-analyse` | Bulk AI analysis |
| POST | `/batch/crm-push` | Bulk CRM push |
| GET | `/webhooks` | List webhook endpoints |
| POST | `/webhooks` | Register webhook |
| GET | `/analytics/overview` | Status/type counts |
| GET | `/analytics/top-industries` | Industries by count |
| GET | `/analytics/ai-score-histogram` | Score distribution |

Full interactive docs: `http://localhost:8000/docs`

## Data Model

Core entity: `Company` (`app/models/company.py`)

- `status`: `discovered` → `needs_review` → `verified` / `rejected` / `contacted` / `suppressed`
- `lead_type`: `no_website_candidate` / `weak_website_candidate` / `website_exists_not_target` / `invalid_or_risky`
- `can_export`: `True` only for verified leads
- `website_opportunity_score`: 0–100 (higher = better lead)

## Compliance

- Audit log written on every status change (`app/services/compliance_service.py`)
- GDPR suppression list (`app/models/suppression.py`)
- Crawler respects `robots.txt` and identifies itself honestly
- No scraping of personal data beyond publicly listed business info

## Testing

```bash
pytest tests/ -v
pytest tests/test_ai_service.py   # AI integration tests (requires ANTHROPIC_API_KEY)
```
