# ARCHITECTURE — Architektur und End-to-End-Datenfluss

**Stand:** 2026-08-16 · Alle Angaben aus dem Code rekonstruiert, nicht aus Dokumentation.

---

## 1. Die zentrale Architektur-Tatsache

Das Repository enthält **zwei getrennte Systeme**, die nie miteinander sprechen:

```
┌─────────────────────────────────────────┐   ┌─────────────────────────────────────────┐
│ SYSTEM A — app/                         │   │ SYSTEM B — backend/                     │
│ "B2B Lead Discovery Service"            │   │ "Autonomous Lead Scraper"               │
│                                         │   │                                         │
│ Quelle:  Google Places API (New)        │   │ Quelle:  beliebige URL                  │
│ Methode: API-Abfrage + eigener Crawler  │   │ Methode: Scrapy / Playwright /          │
│ Extraktion: Regex, deterministisch      │   │          ScrapeGraphAI                  │
│ Ziel:    lokale Firmen OHNE Website     │   │ Extraktion: LLM (OpenAI + Instructor)   │
│ Output:  CSV nach manueller Freigabe    │   │ Ziel:    beliebige B2B-Leads            │
│ DB:      7 Tabellen                     │   │ Output:  CRM-Sync (HubSpot/PD/SF)       │
│ Deploy:  docker-compose (5 Services)    │   │ DB:      2 Tabellen                     │
│ Tests:   77 (nicht lauffähig)           │   │ Deploy:  KEINER                         │
│                                         │   │ Tests:   13 (grün, nur ScrapeGraphAI)   │
└─────────────────────────────────────────┘   └─────────────────────────────────────────┘
        ▲                                                    ▲
        │ HTML-Dashboard (in main.py eingebettet)            │ Next.js-Frontend (frontend/)
        │ /dashboard                                          │ spricht /api/leads, /api/scraper,
        │                                                     │ /api/maps, /api/crm
        └──── KEINE VERBINDUNG ZWISCHEN A UND B ──────────────┘
```

Beide Python-Pakete heissen `app`. Ein gemeinsamer Import in einem Prozess ist unmöglich;
`docker-compose.yml` baut ausschliesslich System A (`build: .`), System B hat ein eigenes,
nirgends referenziertes `backend/Dockerfile`.

**Historische Erklärung** (aus `git log`, 25 Commits, 2026-05-28 bis 2026-08-15):
Die Commits 1–13 bauen System B auf — je ein Commit pro Framework
(„feat: Scrapy spider integration", „feat: Temporal workflow orchestration",
„feat: Apache Airflow DAG", „feat: Streamlit dashboard" …). Ab Commit 14 beginnt mit
„feat: core config and database" der komplette Neubau als System A, diesmal produktorientiert
und compliance-getrieben. **System A ist die zweite, ernsthafte Generation; System B ist ein
Framework-Showcase, der nie stillgelegt wurde.**

---

## 2. Kompaktkette (System A — das Produkt)

```
INPUT            POST /search  { industry, location, radius_km, max_results, keywords[], target }
   │             app/api/searches.py:create_search
   ▼
QUEUE            Search-Row (status="queued") → Celery .delay() → Queue "search"
   │             app/workers/tasks.py:run_search_task
   ▼
API/SCRAPER      Google Geocoding API  → Mittelpunkt (lat/lng)
   │             Google Places API (New) POST places:searchText → max. 20/Seite, paginiert
   │             app/services/places_service.py:search_places
   ▼
VERARBEITUNG     1. Filter business_status != OPERATIONAL         (search_orchestrator)
   │             2. classify_from_place() → LeadType              (website_detection_service)
   │             3. find_duplicate() → 4 Strategien               (dedupe_service)
   │             4. Company + PlaceCandidate anlegen/mergen
   │             5. calculate_score() → 0–100 + Priorität         (scoring_service)
   │             6. evaluate_can_export() → Gate                  (compliance_service)
   │             7. write_audit("discovered")
   ▼
SPEICHERUNG      PostgreSQL: companies, place_candidates, audit_logs
   │
   ▼             ── optionale Vertiefung, nur manuell ausgelöst ──
ENRICHMENT       POST /companies/{id}/crawl    → crawl_company_task → Queue "crawl"
   │               crawler_service.crawl_website()   robots.txt, Crawl-Delay, max. 10 Seiten
   │               extractor_service.extract_from_pages()  Regex, nur explizite Labels
   │               → crawled_pages, contacts
   │             POST /companies/{id}/analyze-website → analyse_website_task → Queue "analyse"
   │               website_quality_service.analyse_website()  HTTPS/Viewport/Kontakt/Baustelle
   │               → Re-Scoring, Re-Gate
   ▼
REVIEW           Mensch im Dashboard: Verify ✓ / Reject ✗ / Contacted 📞 / Suppress 🚫 / Refresh ↻
   │             app/api/reviews.py → compliance_service.mark_*()
   ▼
OUTPUT           GET /export/no-website-candidates → CSV (11 Spalten)
                 app/services/export_service.py — zweite Gate-Prüfung im SQL-WHERE
```

---

## 3. Der Weg eines einzelnen Leads — Schritt für Schritt

Beispiel: Ein Coiffeursalon in Zürich ohne Website.

### Schritt 1 — Suchauftrag entgegennehmen
- **Datei:** `app/api/searches.py`
- **Funktion:** `create_search()`
- **Was passiert:** Pydantic validiert (`SearchCreate`), ein `Search`-Datensatz wird mit
  `status="queued"` in PostgreSQL geschrieben, `run_search_task.delay(search.id)` stellt den Job
  in die Redis-Queue `search`. HTTP 202 geht sofort zurück.
- **Persistenz:** Tabelle `searches`.

### Schritt 2 — Worker übernimmt
- **Datei:** `app/workers/tasks.py`
- **Funktion:** `run_search_task` → `_run_search()` (Celery-Worker `worker-search`, Concurrency 2)
- **Was passiert:** `asyncio.run()` überbrückt Celerys synchrone Welt zur async-Codebasis.
  Der `Search` wird geladen und an `run_search()` übergeben.

### Schritt 3 — Google-Abfrage
- **Datei:** `app/services/places_service.py`
- **Funktionen:** `search_places()` → intern `_geocode_location()`
- **Was passiert:**
  1. `_geocode_location("Zürich")` ruft die **Legacy-Geocoding-API** auf und liefert lat/lng.
     Schlägt sie fehl oder ist leer, greift ein **hartcodierter Fallback auf Zürich**
     (47.3769 / 8.5417) — bei einer Suche in Hamburg würde still in Zürich gesucht.
  2. `POST https://places.googleapis.com/v1/places:searchText` mit `textQuery`
     („Coiffeur Damen Barber Kosmetik in Zürich"), `locationBias.circle` (Radius in Metern),
     `pageSize` ≤ 20, `languageCode: "de"`.
  3. Ein `X-Goog-FieldMask` begrenzt die Antwort auf 10 Felder — kostensenkend und
     ToS-konform (keine Rohdaten-Halde).
  4. Paginierung über `nextPageToken`, bis `max_results` erreicht ist.
- **Ergebnis:** Liste von `PlaceResult`-Objekten.

### Schritt 4 — Klassifizierung
- **Datei:** `app/services/website_detection_service.py`
- **Funktion:** `classify_from_place(place)`
- **Regeln:**
  - kein `websiteUri` → `no_website_candidate` + `EnrichmentStatus.no_website` ← **unser Coiffeur**
  - `websiteUri` auf einer der 18 Social-/Baukasten-Domains (`_SOCIAL_DOMAINS`, u. a. facebook.com,
    instagram.com, linkedin.com, wixsite.com, jimdo.com) → `weak_website_candidate`,
    Grund `no_own_website:<host>`
  - eigene Domain → ebenfalls `weak_website_candidate` (provisorisch, bis zur Qualitätsanalyse)
- **⚠️ Defekt:** `website_exists_not_target` wird hier **nie** zurückgegeben. Der Filter in
  `search_orchestrator.py:66` (`if search.target == "no_website" and lead_type.value ==
  "website_exists_not_target": continue`) ist damit toter Code — jede Firma mit eigener Website
  landet trotzdem in der Datenbank.

### Schritt 5 — Deduplizierung
- **Datei:** `app/services/dedupe_service.py`
- **Funktion:** `find_duplicate()` — vier Strategien in fester Reihenfolge:
  1. `google_place_id` (exakt)
  2. `normalized_domain`
  3. `normalize_phone()` (0041→+41, 0049→+49, 0043→+43)
  4. `normalize_name()` (Akzente entfernt, Rechtsformen GmbH/AG/KG/… gestrippt, lowercase)
- **Bei Treffer:** `merge_into()` füllt nur leere Felder auf, überschreibt nie — und schreibt
  einen `dedupe_merge`-Audit-Eintrag.
- **⚠️ Risiko:** `scalar_one_or_none()` wirft `MultipleResultsFound`, sobald zwei Altbestände
  denselben Namen/dieselbe Nummer tragen → der ganze Suchlauf bricht ab.

### Schritt 6 — Persistenz
- **Datei:** `app/services/search_orchestrator.py`
- **Was entsteht:**
  - `Company` mit `lead_source_type=google_places`, `data_origin="google_places_api"`,
    `status=needs_review`, `google_data_expires_at = jetzt + GOOGLE_DATA_TTL_DAYS`
  - `PlaceCandidate` mit `raw_payload_hash` (SHA-256) **statt** des Google-Rohsatzes — bewusst,
    um die Google-ToS zur Rohdatenspeicherung einzuhalten.

### Schritt 7 — Scoring
- **Datei:** `app/services/scoring_service.py`
- **Funktion:** `calculate_score(ScoreInput)` — rein deterministisch, keine DB, keine KI.
- **Für unseren Coiffeur:** keine Website +40, Telefon +20, Adresse +15, operativ +15,
  Branche relevant +10 = **100 → `high_priority`**.

### Schritt 8 — Compliance-Gate
- **Datei:** `app/services/compliance_service.py`
- **Funktion:** `evaluate_can_export(company, db)` — vier harte Prüfungen:
  1. `status == verified`? → sonst `status_not_verified:needs_review`  ← **hier blockiert**
  2. auf der Suppression-Liste (Company-ID, Place-ID, Domain oder Telefon)?
  3. `no_website_candidate` ohne `verified_at`?
  4. Kontakte mit `is_personal_data=True` ohne `source_url`?
- **Ergebnis:** `can_export=False`, `export_block_reason="status_not_verified:needs_review"`.

### Schritt 9 — Menschliche Review
- **Dateien:** `app/main.py` (`/dashboard`, HTML als String-Konstante), `app/api/reviews.py`
- **Aktion „Verify":** `mark_verified()` setzt `status=verified` + `verified_at=now()`, ruft das
  Gate erneut auf → jetzt `can_export=True`, und schreibt einen `verified`-Audit-Eintrag.

### Schritt 10 — Export
- **Datei:** `app/services/export_service.py`
- **Funktion:** `export_verified_csv()`
- **Was passiert:** SQL filtert erneut auf `status=verified AND can_export=True` (zweite,
  unabhängige Absicherung), erzeugt die 11-spaltige CSV und schreibt **pro exportierter Zeile**
  einen `exported`-Audit-Eintrag.

---

## 4. Nicht verbundene Teile — ausdrückliche Kennzeichnung

| Komponente | Zustand | Beleg |
|---|---|---|
| **Gesamtes System B (`backend/`)** | ❌ nicht mit System A verbunden, kein Compose-Service | `docker-compose.yml` baut nur `build: .` |
| **Next.js-Frontend** | ❌ spricht nur System-B-Endpunkte an (`/api/leads`, `/api/scraper`, `/api/maps`, `/api/crm`) — die es im laufenden Compose-Stack nicht gibt | `frontend/lib/api.ts` vs. `app/main.py` Router |
| **Temporal-Workflow** | ❌ kein Server, kein Worker-Service, nie gestartet | `backend/app/workflows/worker.py` ohne Deployment |
| **Airflow-DAG** | ❌ kein Airflow im Repo; DAG erwartet Pfad `/opt/airflow/backend`, der nirgends erzeugt wird | `backend/dags/lead_pipeline_dag.py:34` |
| **Streamlit-Dashboard** | ❌ kein Service, kein Port | `backend/dashboard.py` |
| **ScrapeGraphAI** | ⚠️ in System B verdrahtet (Route + Celery-Task), aber System B läuft nicht | `backend/app/api/routes/scrapegraph.py` |
| **CRM-Konnektoren** | ⚠️ nur an System-B-Modell `Lead` gebunden — kennen `Company` aus System A nicht | `backend/app/crm/*.py` |
| **`crawl` / `analyze-website`** | ⚠️ existieren, werden aber **nie automatisch** ausgelöst — nur per manuellem POST. Die Pipeline endet faktisch nach Schritt 8. | `search_orchestrator.py` ruft keinen Folge-Task |
| **`data_retention_until` / `google_data_expires_at`** | ⚠️ werden gesetzt, aber von keinem Job ausgewertet | kein Scheduler/Beat im Repo |
| **`Contact`-Review** | ⚠️ Modell + Enum vorhanden, kein Endpunkt | `app/api/` ohne contacts-Router |
| **Scrapling** | ❌ reines Referenzdokument | `docs/scrapling-guide-de.md` |

### Die wichtigste Lücke im Datenfluss

Die Kette **bricht nach Schritt 8 ab**. `run_search_task` löst weder `crawl_company_task` noch
`analyse_website_task` aus. Für `no_website_candidate` ist das korrekt (es gibt nichts zu crawlen),
für `weak_website_candidate` bedeutet es: **Die Website-Qualitätsanalyse — der halbe Produktwert —
läuft nie von selbst.** Jede schwache Website muss ein Mensch einzeln per Klick anstossen.

---

## 5. Laufzeit-Topologie (docker-compose.yml)

| Service | Kommando | Zweck |
|---|---|---|
| `postgres` | postgres:16-alpine | Datenbank, Port 5432 **nach aussen veröffentlicht** |
| `redis` | redis:7-alpine | Celery-Broker + Result-Backend, Port 6379 **veröffentlicht** |
| `api` | `uvicorn app.main:app --reload` | FastAPI, Port 8000 — **`--reload` ist ein Dev-Flag** |
| `migrate` | `alembic upgrade head` | einmalig, `restart: "no"` |
| `worker-search` | Celery `-Q search -c 2` | Google-Suchläufe |
| `worker-crawl` | Celery `-Q crawl -c 4` | Website-Crawls |
| `worker-analyse` | Celery `-Q analyse -c 4` | Qualitätsanalyse |
| `flower` | Celery Flower, Port 5555 | Monitoring, **ohne Authentifizierung** |

**Nicht in Compose:** Queue `refresh` hat **keinen Worker** — `refresh_company_task` wird laut
`app/workers/tasks.py:38` in die Queue `refresh` geroutet, die niemand konsumiert. Der Button
„Refresh ↻" im Dashboard erzeugt Jobs, die **für immer liegen bleiben**.

Ebenfalls nicht in Compose: das gesamte System B, das Next.js-Frontend, Temporal, Airflow,
Streamlit.
