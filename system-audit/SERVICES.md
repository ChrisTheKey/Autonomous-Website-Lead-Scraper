# SERVICES & EXTERNE APIS

**Stand:** August 2026

---

## Aktive externe Services

| Service | Zweck | Datei/Komponente | Status | Env-Variable |
|---|---|---|---|---|
| **Google Places API (New)** | Betriebe finden (searchText) | `app/services/places_service.py`, `scripts/bern_innendekorateure.py` | ✅ Aktiv, funktioniert | `GOOGLE_MAPS_API_KEY` |
| **Google Geocoding API** | Koordinaten für Radius-Suche | `app/services/places_service.py` | ✅ Aktiv (same key) | `GOOGLE_MAPS_API_KEY` |
| **Anthropic Claude API** | Inhabername-Extraktion aus HTML | `app/services/contact_extractor.py` | ✅ Aktiv, funktioniert | `ANTHROPIC_API_KEY` |
| **Anthropic Claude API** | Lead Scoring + Opportunity-Analyse | `app/services/ai_service.py` | ⚠️ Vorhanden, nur im Vollstack-Modus aktiv | `ANTHROPIC_API_KEY` |
| **Anthropic Claude API** | ScrapeGraphAI Backend (experimentell) | `app/services/scrapegraph_service.py` | 🧪 Experimentell, Fallback | `ANTHROPIC_API_KEY` |
| **Ziel-Websites** | Kontaktdaten crawlen | `app/services/contact_extractor.py`, `crawler_service.py` | ✅ Aktiv | — |

---

## Konfigurierbare CRM-Services (nicht aktiv)

| Service | Zweck | Datei | Status | Env-Variable(n) |
|---|---|---|---|---|
| **HubSpot** | Lead-Push ins CRM | `app/services/crm_service.py` | 🔵 Konfigurierbar, ungetestet in Prod | `HUBSPOT_API_KEY` |
| **Salesforce** | Lead-Push ins CRM | `app/services/crm_service.py` | 🔵 Konfigurierbar, ungetestet in Prod | `SALESFORCE_USERNAME`, `SALESFORCE_PASSWORD`, `SALESFORCE_SECURITY_TOKEN`, `SALESFORCE_DOMAIN` |
| **Pipedrive** | Lead-Push ins CRM | `app/services/crm_service.py` | 🔵 Konfigurierbar, ungetestet in Prod | `PIPEDRIVE_API_TOKEN`, `PIPEDRIVE_DOMAIN` |

---

## Interne Services / Infrastruktur

| Service | Zweck | Datei | Status |
|---|---|---|---|
| **PostgreSQL 16** | Persistente Lead-Datenbank | `app/database.py`, `docker-compose.yml` | ⚠️ Vorhanden, nur im Vollstack-Modus |
| **Redis 7** | Celery Broker + Result Backend | `docker-compose.yml` | ⚠️ Vorhanden, nur im Vollstack-Modus |
| **Celery 5** | Async Task Queue (scrape, crawl, analyse) | `app/workers/tasks.py` | ⚠️ Vorhanden, nur im Vollstack-Modus |
| **Playwright / Chromium** | JS-schwere Websites crawlen | `app/services/crawler_service.py` | ⚠️ Installiert, nur bei Bedarf aktiv |
| **Flower** | Celery Monitoring UI (Port 5555) | `docker-compose.yml` | ⚠️ Nur im Docker-Modus |

---

## Experimentelle Services (backend/ Stack)

| Service | Zweck | Datei | Hinweis |
|---|---|---|---|
| **OpenAI GPT** | Alternative AI-Extraktion | `backend/app/ai/openai_agents.py` | Nie aktiv verwendet |
| **LangChain** | Alternative AI-Chain | `backend/app/ai/langchain_chain.py` | Nie aktiv verwendet |
| **LlamaIndex** | Dokumenten-Suche | `backend/app/ai/llama_index_search.py` | Nie aktiv verwendet |
| **Scrapy** | Alternative Scraping-Engine | `backend/app/scrapers/spiders/lead_spider.py` | Nie aktiv verwendet |
| **Temporal** | Workflow-Orchestrierung | `backend/app/workflows/` | Nie aktiv verwendet |
| **Apache Airflow** | DAG-basierter Pipeline | `backend/dags/lead_pipeline_dag.py` | Nie aktiv verwendet |
| **Streamlit** | Dashboard | `backend/dashboard.py` | Nie aktiv verwendet |

---

## Modell-Konfiguration (Claude)

| Parameter | Wert | Konfiguierbar |
|---|---|---|
| Modell | `claude-opus-4-8` | Ja, via `CLAUDE_MODEL` env var |
| Thinking | `{"type": "adaptive"}` | Nein (hartkodiert) |
| Streaming | Ja | Nein (hartkodiert) |
| Temperatur | 0 (für Namenextraktion) | Nein |
| Max Tokens | 200 (für JSON-Antwort) | Nein |

---

## API-Key Sicherheitsstatus

| Variable | Wo gespeichert | Sicherheit |
|---|---|---|
| `GOOGLE_MAPS_API_KEY` | Nur als Env-Variable (Session) | ⚠️ Nicht in .env gespeichert — geht bei Session-Ende verloren |
| `ANTHROPIC_API_KEY` | Nur als Env-Variable (Session) | ⚠️ Nicht in .env gespeichert — geht bei Session-Ende verloren |
| Alle anderen Keys | `.env.example` (nur Namen) | ✅ Kein Secret im Repo |

**WICHTIG:** Für dauerhaften Server-Betrieb müssen beide Keys in `/opt/lead-scraper/.env` persistiert werden (Datei mit `chmod 600` schützen).
