# SERVICES — APIs, Modelle und externe Services

**Stand:** 2026-08-16
**Wichtig:** Dieses Dokument nennt ausschliesslich **Servicenamen und Namen von
Umgebungsvariablen**. Es enthält keine Schlüssel, Tokens, Passwörter oder `.env`-Werte.

**Secret-Scan-Ergebnis:** Im gesamten Repository wurden **keine hartcodierten Zugangsdaten**
gefunden (gesucht nach OpenAI-, Google-, Slack-Key-Mustern und privaten Schlüsseln). Eine `.env`
existiert im Repo nicht. Einzige Ausnahme mit Handlungsbedarf: `docker-compose.yml` setzt für
PostgreSQL einen trivialen Klartext-Platzhalter als Passwort (siehe KNOWN_ISSUES #4).

---

## 1. Übersicht aller nachweislich verwendeten Services

| Service | Zweck | Verwendende Datei / Komponente | Env-Variable(n) | Status |
|---|---|---|---|---|
| **Google Places API (New)** | Kernquelle: Firmensuche, Website-Status, Telefon, Adresse | `app/services/places_service.py` (`search_places`, `refresh_place`) | `GOOGLE_MAPS_API_KEY`, `GOOGLE_PLACES_BASE_URL` | **produktiv vorgesehen**, nie live ausgeführt |
| **Google Geocoding API (Legacy)** | Ort → lat/lng für `locationBias` | `app/services/places_service.py:_geocode_location` | `GOOGLE_MAPS_API_KEY` | **produktiv vorgesehen**; separate API, muss eigens aktiviert werden |
| **Google Maps Services (Python-SDK)** | Zweiter, unabhängiger Maps-Zugang in System B | `backend/app/ai/maps_client.py` | `GOOGLE_MAPS_API_KEY` | experimentell, dupliziert System A |
| **Google Maps JS API** | Kartenanzeige im Frontend | `frontend/package.json` (`@googlemaps/js-api-loader`, `@googlemaps/google-maps-services-js`) | (Frontend-Key, nicht gesetzt) | experimentell |
| **OpenAI** | LLM-Extraktion, Zusammenfassung, Qualifizierung, Agenten, Embeddings | `backend/app/ai/extractor.py`, `langchain_chain.py`, `pydantic_ai_agent.py`, `openai_agents.py`, `llama_index_search.py` | `OPENAI_API_KEY`, `OPENAI_MODEL` | experimentell, nie ausgeführt |
| **ScrapeGraphAI** | LLM-gesteuertes Scraping (Smart/Multi/Search-Graph) | `backend/app/ai/scrapegraph_client.py`, `api/routes/scrapegraph.py`, `tasks/scrape_tasks.py` | `SCRAPEGRAPH_MODEL`, `_HEADLESS`, `_VERBOSE`, `_TIMEOUT`, `_MAX_RESULTS`, `_RESPECT_ROBOTS` (+ `OPENAI_API_KEY`) | experimentell; **13 grüne Unit-Tests**, kein Live-Lauf |
| **HubSpot** | CRM-Sync (Company + Contact) | `backend/app/crm/hubspot.py` | `HUBSPOT_ACCESS_TOKEN` | experimentell, ungetestet |
| **Pipedrive** | CRM-Sync (Organisation + Person + Deal) | `backend/app/crm/pipedrive.py` | `PIPEDRIVE_API_KEY`, `PIPEDRIVE_COMPANY_DOMAIN` | experimentell, ungetestet |
| **Salesforce** | CRM-Sync (Account + Lead) | `backend/app/crm/salesforce.py` | `SALESFORCE_USERNAME`, `SALESFORCE_PASSWORD`, `SALESFORCE_SECURITY_TOKEN`, `SALESFORCE_DOMAIN` | experimentell, ungetestet |
| **PostgreSQL 16** | Primärspeicher beider Systeme | `app/database.py`, `backend/app/core/database.py`, `docker-compose.yml` | `DATABASE_URL` | **produktiv vorgesehen** |
| **Redis 7** | Celery-Broker + Result-Backend, Cache-Pool in System B | `app/workers/tasks.py`, `backend/app/core/redis_client.py`, `docker-compose.yml` | `REDIS_URL`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND` | **produktiv vorgesehen** |
| **Celery + Flower** | Task-Queue und deren Monitoring (Port 5555) | `app/workers/tasks.py`, `backend/app/tasks/celery_app.py`, Compose | s. o. | produktiv vorgesehen; **Flower ohne Auth** |
| **Temporal** | Workflow-Orchestrierung scrape→enrich→qualify→CRM | `backend/app/workflows/` | `TEMPORAL_HOST`, `TEMPORAL_NAMESPACE` | experimentell, **kein Server deployed** |
| **Apache Airflow** | Täglicher Scheduler-DAG | `backend/dags/lead_pipeline_dag.py` | — | experimentell, **kein Airflow vorhanden** |
| **Streamlit** | Alternatives Dashboard für System B | `backend/dashboard.py` | — | experimentell, kein Service |
| **Playwright / Chromium** | Browser-Automation für JS-Seiten | `backend/app/browser/playwright_client.py`, `backend/Dockerfile` | — | experimentell |
| **Scrapy** | Klassischer Spider mit `ROBOTSTXT_OBEY=True` | `backend/app/scrapers/` | — | experimentell |
| **Tailwind CDN** | Styling des eingebetteten Dashboards | `app/main.py:64` (`cdn.tailwindcss.com`) | — | **produktiv im Auslieferungspfad**, externe Laufzeitabhängigkeit |

---

## 2. Ausdrücklich NICHT verwendet

Trotz häufiger Vermutung — im gesamten Repo nicht auffindbar:

- **Anthropic / Claude** — keine Nutzung, kein SDK, kein Key. (`claude-sonnet-4-5` erscheint
  einmalig als Beispielwert in einem ScrapeGraphAI-Test, ohne Aufruf.)
- **Apify**, **Firecrawl**, **n8n**, **Make/Zapier** — nicht vorhanden.
- **Proxy-Dienste**, **Captcha-Löser**, **Stealth-Scraping-Dienste** — nicht vorhanden (laut
  README bewusst ausgeschlossen).
- **E-Mail-Versand** (SMTP, SendGrid, Mailgun, Resend) — nicht vorhanden. Es gibt **keinen
  Outreach-Kanal**; das System endet bei der CSV.
- **Supabase**, **Google Sheets**, **Airtable**, **S3/Cloud Storage** — nicht vorhanden.
- **Vector-DB** (Pinecone, Qdrant, Weaviate, pgvector) — nicht vorhanden. LlamaIndex hält seinen
  Index ausschliesslich im Prozessspeicher.
- **Auth-Provider** (Auth0, Clerk, Keycloak, JWT-Middleware) — nicht vorhanden. **Kein Endpunkt
  ist geschützt.**
- **Monitoring/Error-Tracking** (Sentry, Prometheus, OpenTelemetry) — nicht vorhanden.
- **Hosting/PaaS-Konfiguration** (Vercel, Fly.io, Railway, Kubernetes-Manifeste, Terraform) —
  nicht vorhanden. Deployment existiert nur als lokales `docker-compose.yml`.

---

## 3. Verwendete LLM-Modelle

| Konfiguration | Default | Datei |
|---|---|---|
| `OPENAI_MODEL` | `gpt-4o-mini` | `backend/app/core/config.py` |
| `SCRAPEGRAPH_MODEL` | `openai/gpt-4o-mini` | `backend/app/core/config.py` |

Verwendet in: Instructor-Extraktion, LangChain-Qualifizierung, Pydantic-AI-Agent,
OpenAI-Agents-SDK, LlamaIndex (LLM **und** Embeddings), ScrapeGraphAI.
**Kein Modell wurde je aufgerufen** — es existiert kein API-Key und kein Durchlauf.

---

## 4. Kostenrelevante Beobachtungen vor einer Infrastruktur-Bestellung

1. **Redundanter Geocoding-Call.** `_geocode_location()` steht in `places_service.py` **innerhalb**
   der Paginierungsschleife und wird bei jeder Ergebnisseite erneut aufgerufen. Bei 100 Ergebnissen
   (5 Seiten) sind das 5 statt 1 Geocoding-Anfrage — 5× Kosten für denselben Wert.
2. **Zwei Google-Produkte statt einem.** Places API (New) und die Legacy-Geocoding-API sind
   getrennte SKUs mit getrennter Aktivierung und Abrechnung.
3. **Kein Cache, keine Quota.** Weder Redis-Cache für Places-Antworten noch ein Limit pro
   Tag/Nutzer. `max_results` ist auf 500 pro Suche begrenzt — die Anzahl Suchen ist unbegrenzt.
   Die API ist **unauthentifiziert** erreichbar: Jeder, der den Port erreicht, kann beliebig
   Google-Kosten auf Ihrer Rechnung erzeugen.
4. **`GOOGLE_DATA_TTL_DAYS` wird gesetzt, aber nie ausgewertet.** Es gibt keinen Job, der
   abgelaufene Daten auffrischt oder löscht — nur einen manuellen Button.
5. **Drei CRM-SDKs gleichzeitig** als harte Dependencies (`hubspot-api-client`,
   `simple-salesforce` + HTTPX für Pipedrive), obwohl höchstens eines gebraucht wird.
6. **ScrapeGraphAI + LangChain + LlamaIndex + Instructor + Pydantic-AI + OpenAI-Agents-SDK**
   sind sechs sich überschneidende LLM-Frameworks in einem `requirements.txt`. Das vergrössert
   Image, Build-Zeit und Angriffsfläche erheblich, ohne dass eines davon produktiv genutzt wird.

---

## 5. Vollständige Liste der Umgebungsvariablen

### System A — gelesen in `app/config.py`

In `.env.example` dokumentiert: `DATABASE_URL`, `REDIS_URL`, `CELERY_BROKER_URL`,
`CELERY_RESULT_BACKEND`, `GOOGLE_MAPS_API_KEY`, `APP_ENV`, `DEBUG`,
`MAX_RESULTS_PER_SEARCH`, `MAX_PAGES_PER_DOMAIN`, `GOOGLE_DATA_TTL_DAYS`,
`EXPORT_REQUIRES_VERIFICATION`

Nur im Code, **nicht** in `.env.example`: `GOOGLE_PLACES_BASE_URL`,
`CRAWLER_TIMEOUT_SECONDS`, `CRAWLER_USER_AGENT`

⚠️ `EXPORT_REQUIRES_VERIFICATION` wird in `config.py` definiert und in `docker-compose.yml`
gesetzt, aber **an keiner Stelle im Code gelesen** (verifiziert) — die Verifikationspflicht ist
in `compliance_service.py` hart verdrahtet. Die Variable erweckt den Eindruck, das Gate liesse
sich abschalten; das ist nicht der Fall.

### System B — gelesen in `backend/app/core/config.py`

`APP_NAME`, `DEBUG`, `LOG_LEVEL`, **`SECRET_KEY`** ⚠️, `DATABASE_URL`, `REDIS_URL`,
`OPENAI_API_KEY`, `OPENAI_MODEL`, `SCRAPEGRAPH_MODEL`, `SCRAPEGRAPH_HEADLESS`,
`SCRAPEGRAPH_VERBOSE`, `SCRAPEGRAPH_TIMEOUT`, `SCRAPEGRAPH_MAX_RESULTS`,
`SCRAPEGRAPH_RESPECT_ROBOTS`, `GOOGLE_MAPS_API_KEY`, `HUBSPOT_ACCESS_TOKEN`,
`PIPEDRIVE_API_KEY`, `PIPEDRIVE_COMPANY_DOMAIN`, `SALESFORCE_USERNAME`,
`SALESFORCE_PASSWORD`, `SALESFORCE_SECURITY_TOKEN`, `SALESFORCE_DOMAIN`,
`TEMPORAL_HOST`, `TEMPORAL_NAMESPACE`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`

⚠️ **`SECRET_KEY` ist ein Pflichtfeld ohne Default und fehlt in `.env.example`.** Verifiziert:
`from app.core.config import settings` wirft `ValidationError: secret_key Field required`.
System B kann deshalb nicht starten. Zusätzlich: `SECRET_KEY` wird zwar erzwungen, aber
**nirgends im Code verwendet** — es gibt keine Session-, Token- oder Signaturlogik.

### Frontend

`NEXT_PUBLIC_API_URL` (Default `http://localhost:8000`) — `frontend/lib/api.ts`

---

## 6. Import-Zeit-Instanziierung: das versteckte Betriebsrisiko

Mehrere Module in System B erzeugen ihre API-Clients **auf Modulebene**, also beim Import und
nicht beim ersten Aufruf. Fehlt der jeweilige Key, stirbt der Prozess beim Start statt beim
konkreten Feature:

| Datei | Zeile | Konstrukt | Verifiziert? |
|---|---|---|---|
| `backend/app/ai/extractor.py` | 14 | `AsyncOpenAI(api_key=settings.openai_api_key)` | ✅ **Ja** — wirft `OpenAIError: Missing credentials` bei leerem Key |
| `backend/app/ai/maps_client.py` | 14 | `googlemaps.Client(key=settings.google_maps_api_key)` | ⚠️ aus Code abgeleitet (Paket im Audit-Container nicht installierbar) |
| `backend/app/ai/pydantic_ai_agent.py` | 11 | `OpenAIModel(..., api_key=...)` | ⚠️ aus Code abgeleitet |
| `backend/app/ai/llama_index_search.py` | 11 | `Settings.llm = OpenAI(...)` | ⚠️ aus Code abgeleitet |
| `backend/app/ai/langchain_chain.py` | 11 | `ChatOpenAI(...)` | ⚠️ aus Code abgeleitet |
| `backend/app/crm/hubspot.py` | 15 | `HubSpot(access_token=...)` | ⚠️ aus Code abgeleitet |
| `backend/app/crm/pipedrive.py` | 13 | `_BASE`-URL aus leerem Domain-String gebaut | ✅ trivial nachvollziehbar |

Positiv-Beispiele im selben Repo, die es richtig machen: `backend/app/crm/salesforce.py`
(Lazy-Init via `get_sf()`) und `backend/app/ai/scrapegraph_client.py` (Lazy-Import der Library
+ Konfiguration erst zur Laufzeit).
