# CLAUDE.md

Guidance for Claude Code working in this repository.

**Read `docs/CURRENT_STATE.md` first, every session.** This file describes how to
work here; that file describes where the project currently stands.

## What this repo is

A B2B lead discovery engine for selling websites to local businesses (HWD lead
engine). You enter industry + location + radius; the system finds businesses via
the Google Places API, classifies their web presence, scores the sales
opportunity, and makes leads reviewable and exportable under a compliance gate.

Two economic signals drive it:
1. `no_website` — the business has no website at all.
2. `weak_website` — the business has one, but it is economically inadequate.

## Which implementation is active

- **`app/` is the active implementation.** All work happens here.
- **`backend/` and `frontend/` are legacy.** A superseded earlier attempt
  (Scrapy, Playwright, OpenAI/LangChain agents, CRM connectors, Next.js). It is
  not wired into `docker-compose.yml` and has no tests. Do not touch it unless
  explicitly asked. Note that `.github/workflows/ci.yml` still lints only the
  legacy tree.

## Architecture

```
FastAPI (app/main.py, + inline HTML dashboard at /dashboard)
   │ .delay()
Redis  broker db1 · results db2
   │
Celery workers, one queue each:
   search   → run_search_task        → Google Places + Geocoding
   crawl    → crawl_company_task     → ethical crawler → crawled_pages
   analyse  → analyse_website_task   → quality signals → re-classify + score
   refresh  → refresh_company_task   → re-fetch a place
   │
PostgreSQL — 7 tables, Alembic migrations
```

Layering is API (thin) → services (all logic) → models. Business logic lives in
`app/services/`; `search_orchestrator.py` is the best entry point for
understanding the flow, `app/models/enums.py` for the vocabulary.

External services: **Google Places API (New)** for search and place details, and
the **Geocoding API** for location → lat/lng. Both use `GOOGLE_MAPS_API_KEY`.

## Engineering rules

- **Smallest fix that is structurally sound.** Prefer a clean seam over a
  workaround, but do not refactor beyond the task.
- **Reproduce before fixing.** Prove the failure by execution first, then fix.
- **Do not fix unrelated bugs you notice.** Report them and move on.
- **Test before calling something done.** Add targeted tests for the behaviour
  you changed.
- **Atomic commits**, one concern each, with a body explaining the why.
- **Keep the working tree clean.** Check `git status` before and after.
- Commit and push only when asked.

## Safety and cost

- **Never print secrets**, in full or in part. To verify a key, check length,
  prefix or a hash comparison — never the value.
- **Never commit `.env`.** It is gitignored; keep it that way.
- **External API requests only on explicit approval.** Google Places and
  Geocoding calls cost money; the loop in `places_service.py` also re-geocodes
  per pagination page. Keep `max_results` small in tests.
- **Real crawls only when controlled**, one target at a time. `robots.txt`,
  rate limits and blocked paths are respected by design — do not weaken them.
- **Destructive DB actions only on approval.** No dropping, truncating or
  bulk-updating existing rows; the current data is an experimental record.

## Verification principle

**A verifier outranks an agent's self-report.** Claims must be backed by
executed commands, real output, or a direct read of the DB or code. If something
cannot be verified, say UNKNOWN rather than guessing.

**Never weaken or delete an existing test to make a run green.** If a test
fails, either the code is wrong or the test is wrong — determine which, say so,
and leave it alone unless fixing it is the task.

## Commands verified to work in this repo

```bash
docker compose up -d postgres redis                  # infrastructure
docker compose up -d --force-recreate api            # API on :8000
docker compose up -d --force-recreate worker-search worker-crawl worker-analyse
alembic upgrade head                                 # migrations
uvicorn app.main:app --reload                        # API without Docker
```

Containers do not pick up code changes to Celery config without
`--force-recreate`.

**Test suite caveat:** `pytest tests/` currently fails at fixture setup for every
test. `tests/conftest.py` requires a PostgreSQL database named
`lead_discovery_test`, which neither `docker-compose.yml` nor the migration
creates, and its `setup_db` fixture is `autouse` — so even tests that need no
database error out. The DB-free tests do pass when run without that conftest.
This is a known infrastructure gap, not a code failure.
