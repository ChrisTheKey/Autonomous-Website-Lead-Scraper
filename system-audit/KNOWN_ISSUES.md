# KNOWN_ISSUES — Baustellen, technische Schulden und Risiken

**Stand:** 2026-08-16
**Legende:** ✅ = durch Ausführung verifiziert · 📖 = aus dem Code belegt, nicht ausgeführt

---

## KRITISCH — blockiert den Betrieb oder ist ein Rechts-/Sicherheitsrisiko

### K1 ✅ System A startet nicht: reserviertes Attribut `metadata`
**Datei:** `app/models/audit_log.py:15`
```python
metadata: Mapped[dict | None] = mapped_column(JSONB)
```
`metadata` ist in SQLAlchemy Declarative reserviert (`Base.metadata`). Verifiziert:
```
sqlalchemy.exc.InvalidRequestError: Attribute name 'metadata' is reserved
    when using the Declarative API.
```
**Wirkungskette:** `app.models.audit_log` → `app.models` → `compliance_service` → alle Services →
alle Router → `app.main`. **Die API kann nicht hochfahren.** Ebenso scheitern alle Celery-Tasks,
sobald sie ihre Lazy-Imports ausführen.
**Fix:** Attribut in `metadata_` (oder `meta`) umbenennen und die Spalte explizit benennen:
`mapped_column("metadata", JSONB)`. Die Migration bleibt unverändert; **kein DB-Umbau nötig.**
Aufrufer anpassen: `compliance_service.write_audit()` (Keyword `metadata=`) und alle
`write_audit(..., metadata={...})`-Aufrufe in `workers/tasks.py` und `search_orchestrator.py`.
**Aufwand:** ~30 Minuten.

### K2 ✅ Die gesamte Testsuite von System A ist nicht ausführbar
**Dateien:** `tests/conftest.py:11` (`from app.main import app`) + Folgefehler aus K1.
**Belegt:** `pytest tests/` bricht beim *Collect* ab — **alle 77 Testfunktionen** in 8 Dateien
(classification 12, crawler 13, places 12, scoring 12, dedupe 10, extractor 10, compliance 5,
suppression 3) laufen **kein einziges Mal**. Auch die reinen Logik-Tests ohne DB-Bedarf sind
betroffen, weil `conftest.py` global importiert wird.
**Wirkung:** Der zentrale Qualitäts- und Compliance-Anspruch des Projekts ist **nie verifiziert
worden**. Das README behauptet auf Zeile 145 f. eine Testabdeckung, die faktisch nicht existiert.
**Fix:** nach K1 automatisch erledigt; zusätzlich DB-Fixtures von den Logik-Tests entkoppeln.

### K3 ✅ System B startet nicht: `SECRET_KEY` ist Pflicht und undokumentiert
**Datei:** `backend/app/core/config.py:9` — `secret_key: str = Field(..., min_length=16)`
**Verifiziert:** `ValidationError: secret_key Field required`. Die Variable fehlt in
`.env.example` (0 Treffer). Zusätzlich: `SECRET_KEY` wird **nirgends im Code verwendet** —
es gibt keine Session-, Signatur- oder Tokenlogik, die ihn bräuchte.
**Fix:** entweder in `.env.example` aufnehmen **oder** — sauberer — das Feld entfernen, solange
es keine Funktion hat.

### K4 ✅ Keine Authentifizierung auf irgendeinem Endpunkt
**Dateien:** `app/main.py`, `backend/app/main.py` — beide ohne Auth-Dependency, beide mit
`CORSMiddleware(allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])`.
**Konkret ungeschützt erreichbar:**
- `GET /export`, `GET /export/no-website-candidates` → **CSV mit personenbezogenen Daten**
- `DELETE /companies/{id}` → Datenlöschung
- `POST /search` → **erzeugt kostenpflichtige Google-API-Aufrufe**
- Flower auf Port 5555 → Task-Introspektion
- PostgreSQL 5432 und Redis 6379 sind in Compose **nach aussen veröffentlicht**
**Wirkung:** Auf einem öffentlichen Server ist das ein DSGVO-Vorfall am ersten Tag plus ein
offenes Kostenrisiko. **Ohne Auth darf dieser Stack keinen öffentlichen Server sehen.**
**Fix:** API-Key- oder OAuth-Middleware, CORS auf konkrete Origins, DB-/Redis-Ports nur intern,
Flower hinter Basic-Auth.

### K5 📖 Zwei Systeme, ein Paketname, zwei Migrationsstränge
Beide Stacks heissen `app`; beide Alembic-Historien beginnen mit Revision `0001` ohne
gemeinsame Basis. Auf derselben Datenbank überschreiben sie sich gegenseitig in
`alembic_version`. Ein gemeinsamer Prozess/Container ist unmöglich.
**Wirkung:** Blockiert jede saubere Deployment-Entscheidung. **Muss vor der
Infrastruktur-Bestellung entschieden werden** (siehe „Empfohlene Reihenfolge").

### K6 📖 System B unterläuft sämtliche Datenschutz-Zusagen von System A
`backend/app/models/lead.py` speichert `raw_html` (bis 50.000 Zeichen) unbefristet, ohne
Compliance-Gate, ohne Audit-Log, ohne Sperrliste, ohne `is_personal_data`-Flag und ohne
Retention. Das steht im direkten Widerspruch zum README-Abschnitt *„What Is Deliberately NOT
Implemented"* und zur Architektur von System A.

---

## HOCH

### H1 📖 Der Queue-Name `refresh` hat keinen Worker
`app/workers/tasks.py:38` routet `refresh_company_task` auf die Queue `refresh`.
`docker-compose.yml` startet Worker für `search`, `crawl`, `analyse` — **nicht** für `refresh`.
**Wirkung:** Der Dashboard-Button „Refresh ↻" legt Jobs an, die niemand ausführt. Das ist
zugleich der einzige Mechanismus zur Auffrischung abgelaufener Google-Daten.

### H2 📖 Die Pipeline endet nach der Klassifizierung
`search_orchestrator.run_search()` stösst **keinen** Folge-Task an. `crawl_company_task` und
`analyse_website_task` laufen ausschliesslich auf manuellen Klick.
**Wirkung:** Für `weak_website_candidate` — die halbe Produktidee — findet die Qualitätsanalyse
im Normalbetrieb nie statt. Der Score bleibt auf dem groben Places-Wert stehen.

### H3 📖 Toter Klassifizierungspfad: `website_exists_not_target`
`website_detection_service.classify_from_place()` gibt diesen Wert **nie** zurück (jede Firma mit
Website wird provisorisch `weak_website_candidate`). Der Filter in `search_orchestrator.py:66`
ist damit wirkungslos: **`target: "no_website"` filtert nichts.** Alle Firmen mit funktionierender
Website landen trotzdem in der Datenbank, verbrauchen Speicher und Review-Zeit.

### H4 📖 Dedupe kann den gesamten Suchlauf abbrechen
`dedupe_service.find_duplicate()` nutzt viermal `scalar_one_or_none()`. Sobald zwei Bestandsfirmen
denselben normalisierten Namen oder dieselbe Telefonnummer haben (bei Filialisten der Normalfall),
wirft SQLAlchemy `MultipleResultsFound` — der Task stirbt mitten im Lauf, bereits verarbeitete
Treffer sind je nach Commit-Zeitpunkt inkonsistent.
**Fix:** `.limit(1)` + `scalars().first()`.

### H5 📖 Kontaktierte Leads bleiben exportierbar
`compliance_service.mark_contacted()` setzt `status=contacted`, ruft aber **nicht**
`evaluate_can_export()` auf — anders als `mark_verified()` und `mark_rejected()`. Der Kommentar
im Code („score will drop due to contacted penalty") beschreibt eine Neuberechnung, die nirgends
stattfindet.
**Wirkung:** `can_export` bleibt `True`, der Score bleibt alt. Mehrfachkontaktierung derselben
Firma wird nicht verhindert — im Kaltakquise-Kontext ein rechtlich relevanter Fehler.

### H6 📖 Google-Kosten sind unbegrenzt und teilweise redundant
- `_geocode_location()` steht **innerhalb** der Paginierungsschleife → 1 Geocoding-Call **pro
  Ergebnisseite** statt einmal pro Suche (`places_service.py:104`).
- Kein Cache, keine Tages-/Nutzerquota, kein Circuit-Breaker.
- `POST /search` ist unauthentifiziert (K4) → beliebig oft auslösbar.

### H7 📖 Stiller Fallback auf Zürich
`places_service._geocode_location()` liefert bei leerem Geocoding-Ergebnis hartcodiert
`{47.3769, 8.5417}`. Eine Suche in „Hamburg" mit unauflösbarem Ort sucht damit **still in Zürich**
— ohne Log-Warnung, ohne Fehler. Falsche Leads ohne erkennbare Ursache.

### H8 ✅ Frontend baut vermutlich nicht
`frontend/Dockerfile` kopiert `.next/standalone` und `public/`. Verifiziert fehlen:
`next.config.js`/`next.config.ts` (ohne `output: "standalone"` entsteht kein solches Verzeichnis)
**und** das Verzeichnis `public/`. Beide `COPY`-Schritte schlagen fehl.
Zusätzlich: keine ESLint-Konfiguration vorhanden, obwohl CI `npm run lint` ausführt.

### H9 📖 Import-Zeit-Instanziierung von API-Clients
Sieben Module in System B erzeugen ihre Clients auf Modulebene (Details in `SERVICES.md`
Abschnitt 6). Ein fehlender Key tötet den Prozessstart statt nur das betroffene Feature.
Verifiziert für `AsyncOpenAI(api_key="")` → `OpenAIError`.

---

## MITTEL

### M1 📖 Sechs überlappende LLM-Frameworks
`langchain`, `llama-index`, `instructor`, `pydantic-ai`, `openai-agents`, `scrapegraphai`,
dazu `langextract` — alle als harte Dependencies in `backend/pyproject.toml`, keines produktiv.
Konsequenz: riesiges Image, lange Builds, grosse Angriffsfläche, teure Upgrades.

### M2 📖 Drei CRM-SDKs parallel
HubSpot, Pipedrive, Salesforce gleichzeitig als Pflicht-Dependencies, obwohl höchstens eines
gebraucht wird. Vor einer CRM-Bestellung: eines wählen, zwei entfernen.

### M3 📖 Vier Orchestrierungs-Ebenen für dieselbe Aufgabe
Celery (System A) + Celery (System B) + Temporal + Airflow. Drei davon ohne Deployment.
Das ist die grösste unnötige Komplexität im Repo.

### M4 📖 Fehlende Indizes für die Haupt-Queries
`ORDER BY website_opportunity_score DESC` (jede Listenansicht), `companies.phone` (Dedupe),
`contacts.is_personal_data` (jede Gate-Prüfung), `(status, can_export)` (Export) — alle ohne
Index. Details in `DATA_STORAGE.md` Abschnitt 5.

### M5 📖 Verbindungspool-Mathematik überschreitet PostgreSQL-Default
10 Worker-Prozesse × (pool_size 10 + overflow 20) + API ≈ 330 mögliche Verbindungen gegen
`max_connections = 100`. Braucht PgBouncer oder kleinere Pools — **relevant für die
Server-Dimensionierung**.

### M6 📖 Dashboard hängt an einem externen CDN
`app/main.py:64` lädt Tailwind von `cdn.tailwindcss.com`. Ohne Internet ist das Dashboard
unbrauchbar; zusätzlich ein Drittanbieter im Auslieferungspfad (CSP/Datenschutz).

### M7 📖 Dashboard ist eine 200-Zeilen-HTML-Konstante in `main.py`
Kein Template, kein Build, kein Test, kein Syntax-Highlighting. Änderungen erzwingen einen
Neustart der API.

### M8 📖 Toter Ausdruck im Scoring
`scoring_service.py:39` — `return max(0, 0 - 50), LeadPriority.blocked` ergibt immer `0`.
Die Absicht („−50 für unverifizierte Quelle") ist im Code nicht mehr erkennbar.

### M9 📖 Fragile String-Logik als Klassifizierungsträger
`workers/tasks.py:_analyse_website` leitet `has_own_domain` aus
`weak_website_reason.startswith("no_own_website")` ab. Eine Textänderung an einer anderen Stelle
verändert still das Scoring. Der Grund gehört in ein eigenes Feld oder Enum.

### M10 📖 Kein Retention-/TTL-Job
`data_retention_until` und `google_data_expires_at` werden geschrieben, aber von niemandem
gelesen. Das Löschversprechen des README ist unimplementiert. Es gibt keinen Celery-Beat.

### M11 ✅ CI prüft fast nichts
`.github/workflows/ci.yml` führt nur `ruff` (nur `backend/`) und `next lint` aus.
**Keine Tests**, **kein mypy** (obwohl `strict = true` konfiguriert ist), und das Verzeichnis
`app/` — der gesamte Produktcode — wird **überhaupt nicht geprüft**. Aktueller Ruff-Stand in
`backend/`: 11 offene Verstösse.

### M12 ✅ Kein `main`-Branch
`git ls-remote` zeigt vier Feature-Branches (`claude/…` ×3, `giuliano/lead-scraper-development`)
und **keinen Default-Branch**. Es gibt keinen kanonischen Stand, gegen den deployt werden könnte.

---

## NIEDRIG

| # | Befund | Ort |
|---|---|---|
| N1 | `EXPORT_REQUIRES_VERIFICATION` wird konfiguriert, aber nie gelesen (Verifikation ist hart verdrahtet) | `app/config.py` |
| N2 | `confidence_score` auf `Company` wird nie geschrieben | `app/models/company.py` |
| N3 | `Contact.review_status` hat kein API zum Setzen | `app/api/` |
| N4 | Ungenutzte Variablen/Importe (`homepage_page`, `first_page_html`, `BeautifulSoup` in `extractor_service`, `datetime` in `website_quality_service`) | mehrere |
| N5 | `LeadStatus(str, enum.Enum)` statt `StrEnum` (Ruff UP042) | `backend/app/models/lead.py:10` |
| N6 | `pipelines.py` nutzt `__import__("sqlalchemy", fromlist=["select"])` statt eines normalen Imports | `backend/app/scrapers/pipelines.py:20` |
| N7 | Zufällige User-Agent-Rotation im Scrapy-Middleware — kosmetisch, aber im Widerspruch zur „ehrlichen Identifikation" von System A | `backend/app/scrapers/middlewares.py` |
| N8 | Kein `LICENSE`, kein `CONTRIBUTING`, keine ADRs | Repo-Root |
| N9 | `docker-compose.yml` nutzt das veraltete `version: "3.9"`-Feld | Root |
| N10 | Keine Health-Checks für `api`/Worker in Compose (nur für Postgres/Redis) | `docker-compose.yml` |

---

## Vor einem Server-/Infrastruktur-Umzug zwingend bereinigen

| Was | Warum | Priorität |
|---|---|---|
| `--reload` und `volumes: .:/app` aus dem Compose entfernen | Dev-Konfiguration; Code-Mount macht das Image bedeutungslos | KRITISCH |
| Trivialer Klartext-Default für das DB-Passwort | Muss aus einem Secret-Store kommen | KRITISCH |
| Ports 5432/6379/5555 nicht mehr veröffentlichen | Datenbank und Broker gehören ins interne Netz | KRITISCH |
| Auth + CORS-Einschränkung einziehen | Personendaten-Export und Kostenauslösung offen | KRITISCH |
| System A **oder** B stilllegen | Zwei Schemata, ein Paketname, zwei Migrationen | KRITISCH |
| `main`-Branch etablieren | Kein deploybarer kanonischer Stand | HOCH |
| Worker für Queue `refresh` ergänzen oder Route ändern | Jobs versanden lautlos | HOCH |
| Pool-Grössen / PgBouncer festlegen | 330 potenzielle Verbindungen vs. Default 100 | MITTEL |
| Ungenutzte Frameworks entfernen (Temporal, Airflow, Streamlit, 5 LLM-SDKs, 2 CRM-SDKs) | Bild-Grösse, Build-Zeit, Angriffsfläche, Wartung | MITTEL |
| Tailwind lokal bündeln | Externe Laufzeitabhängigkeit im Dashboard | MITTEL |

---

## Empfohlene Reihenfolge (vor jeder Bestellung)

1. **Produktentscheidung: System A oder System B.**
   Empfehlung auf Basis des Codes: **System A behalten**, System B in ein Archiv-Branch
   verschieben und aus `main` entfernen. System A ist das jüngere, produktnähere und einzige
   compliance-fähige System; das Next.js-Frontend müsste dann auf dessen Endpunkte umgeschrieben
   oder ebenfalls verworfen werden (das eingebettete Dashboard deckt den Anwendungsfall bereits ab).
2. **K1 + K3 beheben** (~1 Stunde): `metadata` umbenennen, `SECRET_KEY` klären.
3. **Die 77 Tests einmal grün sehen** und CI so erweitern, dass sie bei jedem Push laufen —
   inklusive Linting von `app/`.
4. **Einen einzigen echten End-to-End-Durchlauf** mit gültigem Google-Key fahren und das Ergebnis
   (CSV + Company-JSON) als Golden-File im Repo ablegen. Erst danach ist die Dimensionierung von
   Server, DB und Queue seriös schätzbar.
5. **Die Guardrails maschinenlesbar machen:** eine `CLAUDE.md` bzw. `ARCHITECTURE_RULES.md`, die
   die heute nur in Docstrings verstreuten Regeln (robots.txt, keine Namenserfindung,
   Export-Gate, Suppression, TTL) an einer Stelle festhält. Das ist die günstigste Massnahme im
   ganzen Katalog und verhindert, dass die nächste Ausbaustufe die Compliance still aushebelt.
