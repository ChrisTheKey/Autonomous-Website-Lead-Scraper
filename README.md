# Autonomous B2B Lead Discovery Service

**Legal, compliant lead discovery for local businesses without websites.**

You enter: industry + location + radius → the system finds businesses with no website,
scores them as website-sale leads, and makes them reviewable and exportable.

---

## What This Is

A production-near MVP for selling websites to local businesses.
The primary lead type is `no_website_candidate`:
a local business visible on Google Places with no `website_uri`, a phone number, and an address.

---

## Quick Start (Docker Compose)

```bash
cp .env.example .env
# Fill in GOOGLE_MAPS_API_KEY

docker compose up -d postgres redis
docker compose run --rm migrate        # Run Alembic migrations
docker compose up -d api worker-search worker-crawl worker-analyse flower
```

Open: http://localhost:8000/dashboard

API docs: http://localhost:8000/docs

Celery monitoring: http://localhost:5555

---

## Migrations

```bash
# Apply
alembic upgrade head

# Create new
alembic revision --autogenerate -m "description"
```

---

## Starting the API (local dev)

```bash
pip install -r requirements.txt
cp .env.example .env   # fill in values

alembic upgrade head
uvicorn app.main:app --reload
```

---

## Example: POST /search

```bash
curl -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{
    "industry": "Coiffeur",
    "location": "Zürich",
    "radius_km": 10,
    "max_results": 100,
    "keywords": ["Damen", "Barber", "Kosmetik"],
    "target": "no_website"
  }'
```

Response: `202 Accepted` with search ID. Processing runs async via Celery.

---

## Dashboard

Navigate to `/dashboard` for the visual review UI.

Tabs:
- **No Website (High)** — score ≥ 70, no website → ideal leads
- **No Website (Medium)** — score 40–69
- **Weak Website** — has website but low quality
- **Needs Review / Verified / Contacted / Rejected / Suppressed**

Actions per lead: Verify ✓ · Reject ✗ · Mark Contacted 📞 · Suppress 🚫 · Refresh ↻

---

## Example: Export Verified No-Website Leads

```bash
# CSV export — only verified, non-suppressed leads
curl http://localhost:8000/export/no-website-candidates -o leads.csv

# All verified leads
curl "http://localhost:8000/export" -o leads.csv
```

Export is blocked unless `status = verified` AND `can_export = true`.

---

## Lead Classification

| Type | Meaning | Priority |
|---|---|---|
| `no_website_candidate` | No website in Google Places | High — primary lead |
| `weak_website_candidate` | Has website, but social-only / broken / no HTTPS | Medium |
| `website_exists_not_target` | Working own website | Low |
| `invalid_or_risky` | Unclear source, unclassifiable | Blocked from export |

---

## Scoring (0–100)

**No-Website Lead:**
- No website: +40
- Phone available: +20
- Address available: +15
- Business operational: +15
- Industry relevant: +10
- Contacted: −40 | Suppressed: −100 | Unverified source: −50

**Weak-Website Lead:**
- No own domain: +35 | No HTTPS: +15 | Unreachable: +25
- No mobile viewport: +15 | No contact page: +10
- Modern functioning website: −60

**Priority buckets:** ≥70 = high · 40–69 = medium · <40 = low

---

## As a ZERO child agent

This repository is a child agent of **HWD-ZERO**, the operator. ZERO decides when
it runs, with what input, and under which permissions.

```
HWD-ZERO
└── Autonomous-Website-Lead-Scraper   department: acquisition
```

`agent.yaml` is the manifest ZERO reads. `zero_agent/` is the surface it invokes:
one JSON invocation on stdin, one JSON object as the last line of stdout.

```bash
echo '{"action":"health"}' | python -m zero_agent
echo '{"action":"analyse","payload":{"candidates":[
  {"name":"Umzug Bern GmbH","lead_type":"no_website_candidate",
   "has_phone":true,"has_address":true}]}}' | python -m zero_agent
```

| action | capability | does |
| --- | --- | --- |
| `health` | `repo.read` | reports which subsystems are configured |
| `capabilities` | `repo.read` | lists the actions it supports |
| `analyse` | `repo.read` | scores candidates with this repository's real rules |
| `search_leads` | `network.read` | a live Places search |
| `persist_leads` | `database.write` | writes scored leads — **approval-gated** |
| `prepare_outreach` | `repo.read` | drafts outreach, never sends |

### It runs without the database layer

`zero_agent/pure.py` loads `app/models/enums.py` and
`app/services/scoring_service.py` directly from their files. Both are
dependency-free, but `app/models/__init__.py` eagerly imports every ORM model, so
a normal import would pull SQLAlchemy, asyncpg and the whole database layer into
memory just to score a list. On a laptop that is also running a model, that is
the wrong trade. The loader fails loudly if either module ever gains a real
dependency, so this cannot rot silently.

That is why `zero_agent/tests/` has its own conftest: `tests/conftest.py` builds
a live Postgres schema in a session-scoped autouse fixture, and inheriting it
would make "runs without the database layer" untestable.

```bash
pip install pytest pyyaml pydantic pydantic-settings
python -m pytest -q zero_agent/tests        # no Postgres, no Redis, no Celery
```

### It says what it cannot do

An action whose prerequisite is missing returns `unavailable` and exit code 3 —
distinct from a failure, and never accompanied by placeholder data.
`search_leads` without `GOOGLE_MAPS_API_KEY` returns *no* candidates rather than
plausible ones, and ZERO records the reason and continues with the steps that can
run. Invented leads would be worse than none, because they would be acted on.

### Permissions

`network.write` and `external.message` always require the operator's explicit
approval. `persist_leads` uses `database.write`, which is granted but not
autonomous, so ZERO raises a permission gate before it runs. `prepare_outreach`
drafts and never sends; sending is a separate, gated capability this agent does
not hold.

## Running Tests

```bash
pip install -r requirements.txt
pytest tests/ -v
```

Tests cover: classification, scoring, compliance gate, suppression list,
deduplication, Places API (mocked), crawler robots.txt, extractor invariants.

---

## Compliance Architecture

Every action (verify, reject, contact, suppress, export) writes to `audit_logs`.

Export is gated by `compliance_service.evaluate_can_export()`:
- `status` must be `verified`
- `can_export` must be `True`
- Company must not be on suppression list
- `no_website_candidate` requires explicit `verified_at` timestamp
- Contacts with `is_personal_data=True` require `source_url`

Google Places data expires after `GOOGLE_DATA_TTL_DAYS` days.
Refresh via `POST /companies/{id}/refresh`.

---

## What Is Deliberately NOT Implemented

| What | Why |
|---|---|
| Google Maps web scraping | Violates Google ToS |
| LinkedIn scraping | Violates LinkedIn ToS + GDPR |
| Captcha bypass | Illegal in most jurisdictions |
| Proxy rotation for circumvention | Unethical, ToS violation |
| Email guessing (firstname.lastname@...) | GDPR violation, no consent |
| Managing director invention | False data, compliance risk |
| Automatic mass export of unreviewed leads | Compliance risk |
| Storing raw Google API payloads long-term | Violates Google Maps Platform ToS |
| Crawling disallowed paths (robots.txt) | robots.txt is respected as policy |
| Crawling login/admin/cart areas | Unauthorised access risk |

---

## Architecture

```
app/
  main.py            FastAPI app + dashboard
  config.py          Pydantic settings
  database.py        SQLAlchemy async engine
  models/            SQLAlchemy ORM models (7 tables)
  schemas/           Pydantic I/O schemas
  api/               FastAPI routers
  services/
    places_service           Google Places API (New) client
    website_detection        no_website / weak / own classification
    crawler_service          Ethical crawler (robots.txt, rate-limit)
    website_quality          HTTPS, viewport, contact, speed signals
    extractor_service        Business data extraction (no guessing)
    compliance_service       Export gate + audit logging
    dedupe_service           Deduplication + merge
    scoring_service          Opportunity score (deterministic)
    export_service           CSV export (compliance-checked)
    search_orchestrator      End-to-end search pipeline
  workers/tasks.py    Celery async tasks

alembic/             Database migrations
tests/               pytest test suite
docker-compose.yml   Full local stack
```

---

## Data Retention

Set `GOOGLE_DATA_TTL_DAYS` to control how long Google-sourced data is considered fresh.
Expired records are flagged for refresh (`google_data_expires_at`).
Set `data_retention_until` on companies for GDPR deletion scheduling.

Use `DELETE /companies/{id}` for right-to-erasure requests (writes audit log).
