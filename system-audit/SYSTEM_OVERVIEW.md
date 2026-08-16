# SYSTEM_OVERVIEW — Technische Bestandsaufnahme

**Projekt:** Autonomous-Website-Lead-Scraper
**Stand:** 2026-08-16
**Analysierter Branch:** `claude/scrapegraphai-integration-check-wdq9b9`
**Methode:** Statische Analyse aller 126 versionierten Dateien + ausgeführte Import-/Test-Läufe (nur lesend)

> Dieses Dokument ist für die Übergabe an eine dritte Partei geschrieben. Es setzt kein Vorwissen
> über das Projekt voraus. Alle Aussagen sind mit Datei und Zeile belegt. Wo eine Aussage nicht
> durch Ausführung verifiziert werden konnte, ist sie als *(aus Code abgeleitet)* markiert.

---

## 0. Kernaussage in drei Sätzen

Das Repository enthält **zwei vollständig getrennte, nicht miteinander verbundene Lead-Systeme**,
die zufällig denselben Python-Paketnamen `app` benutzen und daher nicht gemeinsam laufen können.
System A (`app/`) ist das im README beschriebene Produkt (Google Places → Klassifizierung →
Compliance-Gate → CSV), System B (`backend/`) ist ein zweiter, älterer Stack (Scrapy/Playwright →
OpenAI → CRM), der von keinem Deployment gestartet wird.
**Beide Systeme sind aktuell nicht lauffähig** — jedes scheitert an einem eigenen, verifizierten
Startfehler (Abschnitt 8 / KNOWN_ISSUES.md).

---

## 1. Repository- und Ordnerstruktur

Vollständiger Baum: siehe `PROJECT_TREE.txt`. Verdichtet:

```
Autonomous-Website-Lead-Scraper/
├── app/                     ← SYSTEM A: "B2B Lead Discovery Service" (~2.500 LOC)
│   ├── main.py                FastAPI-App + eingebettetes HTML-Dashboard (String-Konstante)
│   ├── config.py              Pydantic-Settings (Env-Präfix-frei, .env)
│   ├── database.py            SQLAlchemy Async-Engine + Session-Factory
│   ├── models/                7 ORM-Modelle (searches, companies, place_candidates,
│   │                          crawled_pages, contacts, audit_logs, suppression_list)
│   ├── schemas/               Pydantic-v2 I/O-Schemas
│   ├── api/                   5 Router: searches, companies, reviews, candidates, exports
│   ├── services/              10 Services = die eigentliche Geschäftslogik
│   └── workers/tasks.py       4 Celery-Tasks (search, crawl, analyse, refresh)
├── alembic/                 ← Migration für SYSTEM A (7 Tabellen)
├── tests/                   ← 77 Testfunktionen in 8 Dateien (SYSTEM A)
├── Dockerfile               ← Image für SYSTEM A
├── docker-compose.yml       ← Startet AUSSCHLIESSLICH System A (build: .)
├── requirements.txt         ← Dependencies SYSTEM A (kein LLM, kein Scrapy)
│
├── backend/                 ← SYSTEM B: "Autonomous Lead Scraper" (~1.855 LOC)
│   ├── app/main.py            Eigene FastAPI-App, eigene Router
│   ├── app/core/              config.py, database.py, redis_client.py
│   ├── app/models/lead.py     2 ORM-Modelle (leads, scrape_jobs) — eigenes Schema!
│   ├── app/ai/                extractor (OpenAI+Instructor), langchain_chain,
│   │                          llama_index_search, openai_agents, pydantic_ai_agent,
│   │                          maps_client, scrapegraph_client
│   ├── app/scrapers/          Scrapy-Projekt (Spider, Pipeline, Middleware, settings)
│   ├── app/browser/           Playwright-Client
│   ├── app/crm/               HubSpot, Pipedrive, Salesforce
│   ├── app/tasks/             Eigene Celery-App + 4 Task-Module
│   ├── app/workflows/         Temporal-Workflow + Worker
│   ├── dags/                  Apache-Airflow-DAG
│   ├── dashboard.py           Streamlit-Dashboard
│   ├── alembic/               EIGENE Migration (leads, scrape_jobs)
│   ├── tests/                 13 Tests (nur scrapegraph_client)
│   └── Dockerfile             Eigenes Image (mit Playwright/Chromium) — nicht in Compose
│
├── frontend/                ← Next.js 15 / React 19 UI — spricht nur SYSTEM B an
├── docs/scrapling-guide-de.md  Externes Referenzdokument (nicht Teil der Pipeline)
├── .github/workflows/ci.yml    CI: nur Linting, keine Tests
├── .env.example                Env-Vorlage (unvollständig, s. Abschnitt 8)
└── system-audit/               ← dieses Audit
```

### Funktion der wichtigsten Dateien

| Datei | Funktion | System |
|---|---|---|
| `app/services/places_service.py` | Google Places API (New) Client, Klassifizierungs-Rohdaten, TTL-Berechnung, Payload-Hashing | A |
| `app/services/search_orchestrator.py` | Kern-Pipeline: Suche → Klassifizierung → Dedupe → Persistenz → Scoring → Compliance | A |
| `app/services/website_detection_service.py` | `no_website` / `weak_website` / `own domain` Entscheidung | A |
| `app/services/crawler_service.py` | Eigener höflicher Crawler (robots.txt, Crawl-Delay, Blocklist für Login/Admin/Cart) | A |
| `app/services/extractor_service.py` | Regex-Extraktion aus Crawl-Text; erfindet nachweislich keine Namen (nur explizite Labels) | A |
| `app/services/website_quality_service.py` | HTTPS/Viewport/Kontaktseite/Baustellenseite → `is_weak` | A |
| `app/services/scoring_service.py` | Deterministischer Score 0–100 + Priorität | A |
| `app/services/compliance_service.py` | Export-Gate + Audit-Log + Suppression | A |
| `app/services/export_service.py` | CSV-Export mit zweiter Gate-Prüfung | A |
| `app/workers/tasks.py` | Celery: `run_search_task`, `crawl_company_task`, `analyse_website_task`, `refresh_company_task` | A |
| `backend/app/ai/extractor.py` | LLM-Extraktion aus HTML (OpenAI + Instructor, strukturiert) | B |
| `backend/app/ai/scrapegraph_client.py` | ScrapeGraphAI-Wrapper (Smart/Multi/Search-Graph, robots-Gate) | B |
| `backend/app/tasks/scrape_tasks.py` | Celery: Scrapy-, Playwright- und ScrapeGraphAI-Scrape | B |
| `backend/app/workflows/lead_workflow.py` | Temporal-Orchestrierung scrape→enrich→qualify→CRM | B |
| `backend/dags/lead_pipeline_dag.py` | Airflow-DAG, täglich, 3 hartcodierte Suchanfragen (Berlin/München/Hamburg) | B |

---

## 2. CLAUDE.md und Claude-Code-Instruktionen

**Ergebnis der Suche: es existiert nichts davon.**

Gesucht und **nicht gefunden** wurde (case-insensitive, gesamtes Repo, ohne `.git`/`node_modules`):

| Gesucht | Ergebnis |
|---|---|
| `CLAUDE.md` (beliebige Ebene) | nicht vorhanden |
| `.claude/` Verzeichnis | nicht vorhanden |
| `AGENTS.md`, `*.mdc`, `.cursorrules` | nicht vorhanden |
| `.mcp.json` / `mcp*.json` (MCP-Server-Konfiguration) | nicht vorhanden |
| `settings.json` (Claude-Code-Settings, Hooks, Permissions) | nicht vorhanden |
| Skills-, Hook- oder Slash-Command-Definitionen | nicht vorhanden |
| Dedizierte Prompt-Dateien | nicht vorhanden |

**Was es an prompt-artigen Artefakten tatsächlich gibt** — alles hartcodiert im Quellcode, keine
zentrale Verwaltung, keine Versionierung von Prompt-Änderungen:

| Ort | Inhalt | Rolle |
|---|---|---|
| `backend/app/ai/extractor.py:36-45` | System-Prompt: *„You are a data extraction assistant … Return only what is explicitly present in the HTML."* | Extraktions-Guardrail |
| `backend/app/ai/extractor.py` (`summarize_lead`) | *„Summarize this business lead in 2–3 sentences for a sales team."* | Zusammenfassung |
| `backend/app/ai/langchain_chain.py:14-30` | Qualifizierungs-Prompt (Score 1–10) + Outreach-Prompt (3 Betreffzeilen) | Qualifizierung |
| `backend/app/ai/pydantic_ai_agent.py` | System-Prompt eines `pydantic_ai.Agent` mit `result_type=LeadResearchResult` | Agent-Rolle |
| `backend/app/ai/openai_agents.py` | `Agent` + `@function_tool search_company_info` (OpenAI Agents SDK) | Agent + Tool |
| `backend/app/ai/scrapegraph_client.py:36-47` | `DEFAULT_LEAD_PROMPT` / `DEFAULT_SEARCH_PROMPT`: *„Never guess an email address … leave a field null"* | Extraktions-Guardrail |
| `docs/scrapling-guide-de.md` | 3 fertige Nutzer-Prompts aus einem externen Guide | Referenz, **nicht** im Code verdrahtet |

**Architekturvorgaben / Regeln** existieren ausschließlich als Prosa und Docstrings:

- `README.md` → Abschnitt *„What Is Deliberately NOT Implemented"* (10 explizite Verbote:
  Google-Maps-Scraping, LinkedIn-Scraping, Captcha-Bypass, Proxy-Rotation zur Umgehung,
  E-Mail-Raten, Erfinden von Geschäftsführern, Massenexport ungeprüfter Leads,
  Langzeitspeicherung von Google-Rohdaten, Crawlen verbotener Pfade, Login-/Admin-Bereiche).
- Modul-Docstrings mit „Hard rules" in `compliance_service.py`, `extractor_service.py`,
  `export_service.py`, `places_service.py`, `crawler_service.py`.

**Bewertung:** Die Guardrails sind real im Code umgesetzt (robots.txt-Prüfung, Export-Gate,
`is_personal_data`-Flag, Label-Pflicht bei Namen) — aber sie sind **nirgends maschinenlesbar
dokumentiert**. Für einen neuen Entwickler oder ein Agenten-Setup gibt es keine einzige Datei,
die die Regeln zusammenfasst. Das ist die günstigste offene Lücke im ganzen Projekt (siehe
Empfehlung 5 in KNOWN_ISSUES.md).

---

## 3. Aktueller Workflow

Vollständig in **`ARCHITECTURE.md`** dokumentiert (Kompaktkette, Schritt-für-Schritt-Lauf eines
einzelnen Leads, sowie alle nicht verbundenen Teile).

---

## 4. Echter Beispielinput

Der Input ist an drei Stellen im Projekt real vorhanden und überall identisch belegt
(`app/schemas/search.py:7-13` `examples=`, `README.md:64-74`, `tests/test_classification.py:14-21`,
Dashboard-Formular `app/main.py:75-80`).

### 4.1 HTTP-Input (der einzige produktive Einstiegspunkt von System A)

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

Validierung laut `app/schemas/search.py`:

| Feld | Typ | Regel | Default |
|---|---|---|---|
| `industry` | str | 1–255 Zeichen, Pflicht | — |
| `location` | str | 1–255 Zeichen, Pflicht | — |
| `radius_km` | int | 1–100 | 10 |
| `max_results` | int | 1–500 (zusätzlich global gedeckelt durch `MAX_RESULTS_PER_SEARCH`) | 100 |
| `keywords` | list[str] | optional, wird an den Suchtext angehängt | `[]` |
| `target` | str | Regex `^(no_website\|weak_website\|all)$` | `no_website` |

### 4.2 Interner Input der nächsten Stufe (Google-Places-Rohsatz)

Real im Testcode hinterlegt (`tests/test_places_service.py:11-21`, `tests/test_classification.py:15-23`):

```json
{
  "id": "ChIJabc123",
  "displayName": { "text": "Coiffeur Müller GmbH" },
  "formattedAddress": "Bahnhofstrasse 1, 8001 Zürich",
  "nationalPhoneNumber": "+41 44 123 45 67",
  "businessStatus": "OPERATIONAL",
  "types": ["hair_care"],
  "websiteUri": null
}
```

### 4.3 Input von System B (anderer Einstiegspunkt, anderes Datenmodell)

```bash
curl -X POST http://localhost:8000/api/scraper/ \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com", "use_browser": false, "depth": 1}'
```

---

## 5. Zugehöriger Beispieloutput

### ⚠️ Wichtige Einschränkung

**Es existiert im Repository kein einziger echter, gespeicherter Output.** Verifiziert:
keine `.csv`, `.json`, `.sqlite`, `.db`, keine Fixture- oder Golden-Files, kein `data/`-Ordner,
keine Beispiel-Exporte. Es gibt zusätzlich keinen erfolgreichen Durchlauf, weil beide Systeme
aktuell nicht starten (Abschnitt 8). Die folgenden Strukturen sind daher **aus dem Code
abgeleitete Schemata, keine Messergebnisse** — Werte sind mit `<…>` markiert bzw. maskiert.

### 5.1 Sofort-Antwort auf `POST /search` (HTTP 202)

Schema: `app/schemas/search.py` → `SearchOut`

```json
{
  "id": 1,
  "industry": "Coiffeur",
  "location": "Zürich",
  "radius_km": 10,
  "keywords": ["Damen", "Barber", "Kosmetik"],
  "target": "no_website",
  "max_results": 100,
  "status": "queued",
  "created_at": "<ISO-8601>",
  "updated_at": "<ISO-8601>"
}
```

Die eigentliche Verarbeitung läuft asynchron (`run_search_task.delay(search.id)`).

### 5.2 Lead-Datensatz nach dem Durchlauf (`GET /companies`)

Schema: `app/schemas/company.py` → `CompanyListOut`. Feldwerte laut Scoring-Regeln
(`scoring_service.py`: kein Website +40, Telefon +20, Adresse +15, operativ +15, Branche +10 = 100):

```json
{
  "id": 1,
  "name": "<Firmenname>",
  "industry": "Coiffeur",
  "location": "Zürich",
  "lead_type": "no_website_candidate",
  "status": "needs_review",
  "lead_priority": "high_priority",
  "website_opportunity_score": 100,
  "website_available": false,
  "phone": "<+41…, normalisiert>",
  "address": "<Strasse, PLZ Ort>",
  "can_export": false,
  "export_block_reason": "status_not_verified:needs_review"
}
```

`can_export: false` beim ersten Durchlauf ist **beabsichtigt** — der Export ist bis zur manuellen
Verifikation gesperrt (`compliance_service.evaluate_can_export`).

### 5.3 CSV-Export-Zeile (`GET /export/no-website-candidates`)

Header exakt aus `export_service.py:29-41`, Zeilenaufbau aus `schemas/export.py`:

```csv
company_name,industry,location,phone,address,website_status,lead_type,website_opportunity_score,source_type,verified_at,notes
<Firmenname>,Coiffeur,Zürich,<Telefon>,<Adresse>,no_website,no_website_candidate,100,google_places,<ISO-8601>,<Notiz>
```

### 5.4 Celery-Task-Rückgaben (Rohstruktur aus `app/workers/tasks.py`)

```json
{"search_id": 1, "companies_created": <int>}
{"company_id": 1, "pages_crawled": <int>}
{"company_id": 1, "score": <int>, "is_weak": <bool>}
```

### 5.5 Output von System B

`backend/app/api/routes/scrapegraph.py` → `ScrapedLead`; `backend/app/models/lead.py` → Tabelle `leads`:

```json
{
  "company_name": "<Firmenname>",
  "email": null,
  "phone": "<Telefon>",
  "address": "<Adresse>",
  "city": "<Ort>",
  "country": "<Land>",
  "description": "<ein Satz>",
  "industry": "<Branche>",
  "social_links": []
}
```

---

## 6. APIs und externe Services

Vollständig in **`SERVICES.md`**.

---

## 7. Datenspeicherung

Vollständig in **`DATA_STORAGE.md`**.

---

## 8. Aktueller technischer Stand

### ✅ Stabil / nachweislich funktionierend

| Komponente | Nachweis |
|---|---|
| `scoring_service.py` | Reine Funktion, deterministisch, keine I/O-Abhängigkeit. Importiert fehlerfrei. |
| `places_service.py` (Parsing-Teil) | `PlaceResult`, `is_social_only`, `payload_hash`, `expires_at` importieren und laufen fehlerfrei. |
| `extractor_service.py` | Importiert fehlerfrei; Regex-Logik ohne externe Abhängigkeit. |
| `crawler_service.py` | Importiert fehlerfrei; robots.txt-Logik + Blocklist vollständig implementiert. |
| `website_detection_service.py` | Importiert fehlerfrei. |
| `backend/app/ai/scrapegraph_client.py` | **13 Tests laufen und sind grün** (`cd backend && pytest tests/`) — die einzige real ausführbare Testsuite im Repo. |
| Alembic-Migrationen (beide) | Syntaktisch valide, Enum-Typen sauber definiert. Nicht gegen eine echte DB ausgeführt. |
| Docker-Images | Dockerfiles sind valide (nicht gebaut). |

### 🧪 Experimentell (existiert, aber unbewiesen)

| Komponente | Warum experimentell |
|---|---|
| Gesamtes `backend/` (System B) | Wird von keinem Deployment gestartet, kein Compose-Service, keine Tests ausser scrapegraph. |
| Temporal-Workflow (`backend/app/workflows/`) | Kein Temporal-Server in Compose, kein Worker-Service, nie ausgeführt. |
| Airflow-DAG (`backend/dags/`) | Kein Airflow im Repo/Compose; DAG macht `sys.path.insert("/opt/airflow/backend")` auf einen Pfad, der nirgends erzeugt wird. |
| Streamlit-Dashboard (`backend/dashboard.py`) | Kein Service, kein Port, keine Doku. |
| Next.js-Frontend | Baut vermutlich nicht (fehlende `next.config.js` für `output: "standalone"`, fehlendes `public/`) — siehe KNOWN_ISSUES #7. |
| ScrapeGraphAI-Integration | Code + Tests vorhanden, aber nie gegen eine echte Seite/LLM gelaufen (kein API-Key, `playwright install chromium` nie ausgeführt). |
| LlamaIndex-Suche | Index nur im RAM (`_index` als Modul-Global), keine Persistenz, kein Vector-Store. |
| CRM-Konnektoren (3×) | Kein Test, kein Sandbox-Nachweis, Clients werden teils beim Import instanziiert. |

### 🚧 Baustellen (verifizierte Defekte)

Priorisiert und vollständig in **`KNOWN_ISSUES.md`**. Die vier härtesten:

1. **System A startet nicht.** `app/models/audit_log.py:15` deklariert das Attribut `metadata`,
   das in SQLAlchemy Declarative reserviert ist → `InvalidRequestError`. Verifiziert:
   `import app.main` schlägt fehl → **die API kann nicht hochfahren**.
2. **Die gesamte Testsuite von System A ist tot.** Alle 77 Testfunktionen scheitern bereits beim
   Collect, weil `tests/conftest.py` `app.main` importiert. Das README behauptet Testabdeckung,
   die faktisch nie ausgeführt werden kann.
3. **System B startet nicht.** `backend/app/core/config.py:9` verlangt `secret_key` (Pflichtfeld),
   das in `.env.example` **fehlt** → `ValidationError` beim Import. Verifiziert.
4. **Zwei Systeme, ein Paketname.** Beide Stacks heissen `app` → sie können nicht im selben
   Interpreter/Container koexistieren, und `tests/` vs. `backend/tests/` kollidieren bei einem
   Pytest-Lauf aus dem Repo-Root.

### 📋 Geplant (im Code/Doku vorgesehen, nicht umgesetzt)

| Vorhaben | Fundstelle | Zustand |
|---|---|---|
| `licensed_provider` als Lead-Quelle | `app/models/enums.py` (`LeadSourceType`) | Enum-Wert existiert, kein Konnektor |
| `public_register` als Lead-Quelle | ebd. | Enum-Wert existiert, kein Code |
| `manual_entry` als Lead-Quelle | ebd. | Enum-Wert existiert, kein Endpunkt |
| Contact-Review-Workflow | `ContactReviewStatus`, `Contact.review_status` | Feld + Enum, **kein API-Endpunkt** zum Prüfen von Kontakten |
| PlaceCandidate-Review | `ReviewStatus`, `/candidates` | nur lesend, kein Accept/Reject |
| `confidence_score` auf Company | `models/company.py` | Feld existiert, wird nie geschrieben |
| DSGVO-Löschung / Retention-Job | `data_retention_until`, README | Feld wird gesetzt, **kein Job löscht je etwas** |
| TTL-Refresh von Google-Daten | `google_data_expires_at`, README | Feld wird gesetzt, **kein Scheduler** prüft es (nur manuell per `POST /companies/{id}/refresh`) |
| Scrapling/MCP-Integration | `docs/scrapling-guide-de.md` | reines Referenzdokument, bewusst nicht verdrahtet |

---

## 9. Kritische Architekturprüfung

Vollständig, nach KRITISCH/HOCH/MITTEL/NIEDRIG sortiert, in **`KNOWN_ISSUES.md`**.

---

## 10. Abschlussbericht

**Aktueller Input:**
`POST /search` mit `{industry, location, radius_km, max_results, keywords[], target}` —
real belegt als `Coiffeur / Zürich / 10 km / 100 / [Damen, Barber, Kosmetik] / no_website`.
System B hat einen zweiten, unabhängigen Input: `POST /api/scraper/` mit `{url, use_browser, depth}`.

**Kernprozess:**
Google Places (New) Textsuche → Klassifizierung nach Website-Status → Deduplizierung (Place-ID,
Domain, Telefon, Name) → Persistenz als `Company` + `PlaceCandidate` → deterministisches Scoring
(0–100) → Compliance-Gate → manuelle Review im Dashboard → CSV-Export.
Optionale Vertiefung: eigener robots.txt-treuer Crawler → Regex-Extraktion → Qualitätsanalyse →
Re-Scoring.

**Aktueller Output:**
Kein echter Output vorhanden. Vorgesehen: Company-JSON über `GET /companies` und eine CSV mit
11 festen Spalten über `GET /export/no-website-candidates`.

**APIs/Services:**
Produktiv vorgesehen: Google Places API (New) + Google Geocoding API (Legacy). Im Code, aber
inaktiv: OpenAI, ScrapeGraphAI, HubSpot, Pipedrive, Salesforce, Temporal, Airflow. Infrastruktur:
PostgreSQL 16, Redis 7. Externes CDN: `cdn.tailwindcss.com` im Dashboard.

**Datenspeicherung:**
PostgreSQL, zwei **unverbundene** Schemata: System A mit 7 Tabellen (`companies`, `searches`,
`place_candidates`, `crawled_pages`, `contacts`, `audit_logs`, `suppression_list`), System B mit
2 Tabellen (`leads`, `scrape_jobs`). Zwei getrennte Alembic-Historien, beide mit Revision `0001` —
sie überschreiben sich gegenseitig, wenn sie auf dieselbe Datenbank laufen.

**Was funktioniert:**
Die Geschäftslogik von System A ist sauber geschrieben, deterministisch und testbar:
Scoring, Klassifizierung, Dedupe, Compliance-Gate, Extraktions-Guardrails, höflicher Crawler.
Der ScrapeGraphAI-Wrapper ist der einzige Teil mit grüner, laufender Testabdeckung.

**Was fehlt:**
Lauffähigkeit (beide Systeme starten nicht), jede Form von Authentifizierung, ein einziger
End-to-End-Durchlauf, Testausführung in CI, ein `main`-Branch, Secret-Management,
Retention-/TTL-Jobs und eine Entscheidung, welches der beiden Systeme das Produkt ist.

**Grösste technische Risiken:**
1. Zwei parallele Systeme mit identischem Paketnamen und konkurrierenden DB-Schemata.
2. Kein Auth auf Endpunkten, die personenbezogene Daten ausliefern und exportieren.
3. Der Compliance-Anspruch des Projekts ist nie durch einen laufenden Test abgesichert worden.
4. Google-Kosten sind unbegrenzt: keine Quota, kein Cache, redundanter Geocoding-Call je Seite.
5. Produktionsuntaugliches Compose (Hot-Reload, Code-Volume, offene DB-Ports, trivialer DB-Default).

**Empfohlener nächster Schritt:**
**Vor jeder Server-/CRM-/DB-Bestellung**: eine Produktentscheidung treffen (System A oder B),
die drei Startfehler beheben, die 77 Tests einmal grün sehen und CI sie ausführen lassen.
Das kostet ~1 Arbeitstag und ist die Voraussetzung dafür, dass Infrastruktur überhaupt
sinnvoll dimensioniert werden kann. Details: KNOWN_ISSUES.md → „Empfohlene Reihenfolge".
