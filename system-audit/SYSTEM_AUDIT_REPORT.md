# SYSTEM AUDIT REPORT — Abschlussbericht

**Erstellt:** August 2026  
**Repo:** ChrisTheKey/Autonomous-Website-Lead-Scraper  
**Branch:** claude/trusting-cannon-IHn6a

---

## Kompakte Systemübersicht

**Aktueller Input:**  
Branche + Region (z.B. "Innendekorateur Bern") → direkt in Script oder via API

**Kernprozess:**  
Google Places API → Klassifikation (kein/schwach/social Website) → Scoring → Website Crawl → Claude AI extrahiert Inhabernamen → E-Mail Regex → Excel Export

**Aktueller Output:**  
`exports/bern_innendekorateure.xlsx` — 64 Leads, 61 mit Telefon, 12 mit E-Mail, 10 mit Inhabername

**APIs/Services:**  
Google Places API (New) + Google Geocoding API + Anthropic Claude claude-opus-4-8

**Datenspeicherung:**  
Aktuell: nur lokale Excel/CSV-Dateien. PostgreSQL-Schema vorhanden aber nicht aktiv.

**Was funktioniert:**  
- Google Places Scraping in Echtzeit ✅  
- Website-Klassifikation (no/social/weak/ok) ✅  
- Deterministisches Opportunity Scoring ✅  
- Claude-basierte Inhabernamen-Extraktion ✅  
- E-Mail Extraktion via Regex ✅  
- Excel Export (3-Sheet, professionell) ✅  

**Was fehlt:**  
- Persistente Datenspeicherung (DB läuft nicht)  
- API-Keys persistent gespeichert (gehen bei Session-Ende verloren)  
- Systemd-Services an neuen Server-Pfad angepasst  
- Outreach-Agent Pfad konfigurierbar  
- Frontend nie in Betrieb genommen  
- CRM-Integration ungetestet  

**Grösste technische Risiken:**  
1. API-Keys nicht persistent → Bot startet nach Neustart nicht  
2. Zwei konkurrierende Stacks (app/ vs backend/) → Wartungsaufwand  
3. Hartkodierte Pfade (`/home/chris/`) → schlägt auf neuem Server fehl  
4. Webhook-Speicherung in RAM → geht bei Neustart verloren  
5. Kein Checkpoint bei Scripts → Datenverlust bei API-Ausfall mitten im Run  

**Empfohlener nächster Schritt:**  
Vor Server-Bestellung `K1–K3` aus KNOWN_ISSUES.md lösen (API-Keys persistieren, Pfade korrigieren). Danach ist das System deployment-ready für Hetzner.

---

## Was ist stabil / produktiv

| Komponente | Beschreibung |
|---|---|
| `scripts/bern_innendekorateure.py` | Vollständig funktionsfähig, läuft standalone |
| `app/services/places_service.py` | Google Places Integration, getestet |
| `app/services/contact_extractor.py` | Claude-Namenextraktion, getestet |
| `app/services/scoring_service.py` | Deterministisches Scoring, Unit-Tests vorhanden |
| `app/services/compliance_service.py` | Export-Gate + Audit-Log, Unit-Tests vorhanden |
| `app/services/dedupe_service.py` | Deduplizierung, Unit-Tests vorhanden |
| Excel/CSV Export | openpyxl, funktioniert |

## Was ist experimentell

| Komponente | Beschreibung |
|---|---|
| `app/services/scrapegraph_service.py` | ScrapeGraphAI nicht installiert, wird übersprungen |
| `backend/` Parallelstack | LangChain, Scrapy, Airflow — nie produktiv eingesetzt |
| `frontend/` Next.js | Komponenten vorhanden, nie deployed |
| CRM-Integration | Code vorhanden, Keys fehlen, ungetestet |
| Webhook-System | In-Memory, verliert Daten bei Neustart |

## Baustellen

Siehe `KNOWN_ISSUES.md` für vollständige Liste.  
**Top 5 vor Server-Kauf:**

1. **K1** — API-Keys in `.env` persistieren (30 Min)
2. **K2** — Systemd-Pfade korrigieren (15 Min)  
3. **K3** — Outreach-Pfad konfigurierbar machen (30 Min)
4. **H1** — Entscheidung: backend/ löschen oder integrieren (strategisch)
5. **H2** — Entscheidung: frontend/ löschen oder deployen (strategisch)

## Geplant (im Code referenziert, nicht umgesetzt)

| Feature | Referenz |
|---|---|
| Redis-Persistenz für Webhooks | Kommentar in `webhook_service.py` |
| Vector-DB für Lead-Suche | Impliziert durch LlamaIndex in backend/ |
| Airflow-basierter täglicher Pipeline | `backend/dags/lead_pipeline_dag.py` |
| Temporal-Workflow-Engine | `backend/app/workflows/` |
| Streamlit Dashboard | `backend/dashboard.py` |
| Frontend-UI für Lead-Review | `frontend/` |

---

## Die 5 wichtigsten Dinge vor dem Server-Kauf

### 1. API-Keys persistent machen
```bash
# Auf neuem Server:
cat > /opt/lead-scraper/.env << 'EOF'
GOOGLE_MAPS_API_KEY=[dein Key]
ANTHROPIC_API_KEY=[dein Key]
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/lead_discovery
REDIS_URL=redis://localhost:6379/0
EOF
chmod 600 /opt/lead-scraper/.env
```
Ohne das startet der Bot nicht.

### 2. Systemd-Services korrigieren
`lead-scraper.service` und `lead-scraper-worker.service` müssen `User=root` und `WorkingDirectory=/opt/lead-scraper` bekommen — sonst schlägt `systemctl start` fehl.

### 3. backend/ und frontend/ entfernen oder klarstellen
Diese beiden Ordner enthalten ~50% des Codes, sind aber nie aktiv. Sie erzeugen Verwirrung und erhöhen den Wartungsaufwand. Empfehlung: löschen und in separatem Repo aufbewahren falls später gebraucht.

### 4. Entscheiden: Standalone-Scripts oder Vollstack
**Standalone (aktuell):** Einfach, kein Server nötig, Excel-Output. Gut für manuelles Outreach.  
**Vollstack (FastAPI + Celery + PostgreSQL):** Automatisiert, persistent, API-basiert. Gut für tägliche Automatisierung.  
Für den Hetzner-Server empfiehlt sich der Vollstack-Modus mit Standalone-Scripts als Quick-Tool.

### 5. Outreach-Agent-Anbindung definieren
Der Companion-Agent (`~/Autonomer-Website-Outreach-Agent/`) hat einen hartkodiertem Pfad. Auf dem Server muss entweder:
- Beide Repos auf denselben Server deployen (gemeinsamer Pfad)
- Oder die Verbindung auf eine echte API / Webhook umstellen (robuster)
