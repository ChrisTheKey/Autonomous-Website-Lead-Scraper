# KNOWN ISSUES — Baustellen und technische Risiken

**Stand:** August 2026  
**Prioritäten:** KRITISCH / HOCH / MITTEL / NIEDRIG

---

## KRITISCH

### K1 — API-Keys nicht persistent gespeichert
**Problem:** `GOOGLE_MAPS_API_KEY` und `ANTHROPIC_API_KEY` sind nur als Session-Umgebungsvariablen gesetzt. Bei Server-Neustart, Session-Ende oder neuer Deployment-Umgebung sind sie weg. Der Bot stoppt sofort.  
**Datei:** Kein `.env` mit echten Werten vorhanden  
**Fix vor Server-Deployment:** `.env` mit echten Keys anlegen, `chmod 600` setzen  

### K2 — Systemd-Services hartkodieren Benutzerpfad `/home/chris/`
**Problem:** `lead-scraper.service` und `lead-scraper-worker.service` enthalten `User=chris` und `WorkingDirectory=/home/chris/Autonomous-Website-Lead-Scraper`. Auf einem Hetzner-Server existiert dieser Pfad nicht.  
**Datei:** `lead-scraper.service`, `lead-scraper-worker.service`  
**Fix:** Pfade auf `/opt/lead-scraper` und `User=root` (oder neuen Systembenutzer) anpassen  

### K3 — Companion-Repo-Pfad hartkodiert
**Problem:** `scripts/daily_pipeline.sh` und `export_leads.py` erwarten den Outreach-Agent unter `/home/chris/Autonomer-Website-Outreach-Agent/`. Auf neuem Server nicht vorhanden.  
**Datei:** `scripts/daily_pipeline.sh`, `export_leads.py`  
**Fix:** Pfad konfigurierbar machen (Env-Variable `OUTREACH_AGENT_PATH`)  

---

## HOCH

### H1 — Zwei konkurrierende Tech-Stacks (app/ vs backend/)
**Problem:** `backend/` enthält einen vollständigen Parallel-Stack mit anderem Framework (LangChain, Scrapy, Airflow, OpenAI). Beide haben eigene Celery-Apps, eigene Alembic-Migrationen, eigene Models. Unklar welcher produktiv werden soll.  
**Risiko:** Doppelte Wartung, verwirrend für neue Entwickler, kein gemeinsamer Datenpfad  
**Fix:** Entscheidung treffen: `backend/` entweder integrieren oder löschen  

### H2 — Next.js Frontend nie in Betrieb genommen
**Problem:** `frontend/` enthält ein vollständiges Next.js-Projekt mit TypeScript-Komponenten, aber es gibt keinen Backend-Binding, keine API-Konfiguration für Produktion und keine Docker-Integration im Haupt-`docker-compose.yml`.  
**Risiko:** Toter Code, erzeugt falschen Eindruck  
**Fix:** Entweder deployen oder entfernen  

### H3 — Webhook-Endpoints nur In-Memory gespeichert
**Problem:** `webhook_service.py` speichert registrierte Webhook-URLs im RAM. Bei Neustart des API-Servers sind alle registrierten Webhooks weg.  
**Datei:** `app/services/webhook_service.py` (Kommentar im Code: "Redis would be used in production")  
**Fix:** Webhooks in PostgreSQL oder Redis persistieren  

### H4 — Keine E-Mail-Quote für Claude-Namenextraktion
**Problem:** `contact_extractor.py` ruft Claude für jeden Lead auf (1 API-Call pro Website). Bei 100 Leads = 100 synchrone API-Calls. Kein Rate-Limiting, kein Batch-Modus, kein Caching.  
**Risiko:** Hohe Kosten bei grossem Volumen, mögliche Rate-Limit-Fehler  
**Fix:** Batching oder Caching von Ergebnissen einbauen  

### H5 — ScrapeGraphAI-Paket nicht installiert
**Problem:** `scrapegraph_service.py` importiert `scrapegraphai`, aber das Paket ist nicht in der aktuellen Umgebung installiert. Der Service fällt auf HTML-Fallback zurück — ohne Fehlermeldung.  
**Datei:** `app/services/scrapegraph_service.py`, `requirements.txt` (scrapegraphai>=1.29.0 eingetragen)  
**Fix:** In Produktion `pip install scrapegraphai` sicherstellen, oder Service entfernen (Contact Extractor ersetzt ihn)  

---

## MITTEL

### M1 — Doppelte Kontaktextraktions-Services
**Problem:** Drei Services machen dasselbe (Kontaktdaten aus Website extrahieren):
1. `contact_extractor.py` (neu, Claude-basiert, korrekt)
2. `scrapegraph_service.py` (experimentell, ScrapeGraphAI)
3. `extractor_service.py` (Regex-basiert, für Vollstack-Pipeline)

Kein klarer "primary" Service.  
**Fix:** `contact_extractor.py` als Standard definieren, andere deprecaten  

### M2 — `daily_pipeline.sh` wartet fix 3 Minuten auf Celery
**Problem:** `sleep 180` zwischen Scraping und Export. Wenn Celery länger braucht (langsame Sites, viele Leads), werden unvollständige Daten exportiert.  
**Datei:** `scripts/daily_pipeline.sh`  
**Fix:** Polling auf `search.status == completed` statt Fix-Sleep  

### M3 — CORS komplett offen
**Problem:** `app/main.py` setzt `allow_origins=["*"]`. In Produktion sollte nur die eigene Domain erlaubt sein.  
**Datei:** `app/main.py`  
**Fix:** Auf spezifische Domain einschränken, via Env-Variable konfigurierbar  

### M4 — Kein strukturiertes Error-Handling in Scripts
**Problem:** `scripts/bern_innendekorateure.py` hat kein globales Exception-Handling. Wenn Google API oder Claude API mitten im Lauf ausfällt, gibt es keinen partiellen Output — alles geht verloren.  
**Fix:** Checkpoint-Logik: Ergebnisse nach jeder Branche zwischenspeichern  

### M5 — `bern_innendekorateure.py` hat hartkodierte Queries
**Problem:** Die 8 Suchanfragen (`QUERIES = [...]`) sind hartkodiert. Um eine andere Stadt oder Branche zu scrapen, muss die Datei editiert werden.  
**Fix:** CLI-Parameter (`--city`, `--industry`, `--queries`) hinzufügen  

---

## NIEDRIG

### N1 — Mehrere hartkodierte Schwellenwerte
- Score-Basis-Werte in `scoring_service.py` und `scripts/` (nicht identisch!)
- Radius 15 km in `bern_innendekorateure.py` hartkodiert
- `MAX_RESULTS_PER_SEARCH` in `.env.example` aber nicht überall genutzt

### N2 — Tests laufen nicht in CI (ungeprüft)
**Problem:** `.github/workflows/ci.yml` ist vorhanden, aber ob Tests aktuell grün sind ist unbekannt. In der Remote-Umgebung fehlen PostgreSQL und Redis für Integrationstests.  

### N3 — `exports/` enthält Produktionsdaten im Repo
**Problem:** `exports/.gitignore` sollte Excel/CSV-Dateien ignorieren, aber die aktuellen Exports (`bern_innendekorateure.xlsx`, `.csv`) sind eingecheckt (oder zumindest vorhanden).  
**Fix:** Sicherstellen dass `exports/*.xlsx` und `exports/*.csv` in `.gitignore` stehen  

### N4 — backend/ hat eigene requirements.txt die nicht kompatibel sein muss
**Problem:** `backend/requirements.txt` enthält `openai`, `langchain`, `apache-airflow` etc. — schwere Pakete die nicht zum Kern-Stack gehören. Bei versehentlichem `pip install -r backend/requirements.txt` gibt es Konflikte.  

---

## Checkliste vor Server-Deployment

- [ ] **K1** `.env` mit echten API-Keys anlegen (GOOGLE_MAPS_API_KEY, ANTHROPIC_API_KEY, DATABASE_URL, REDIS_URL)
- [ ] **K2** Systemd-Services auf neuen Pfad `/opt/lead-scraper` anpassen
- [ ] **K3** Outreach-Agent-Pfad konfigurierbar machen
- [ ] **H1** Entscheidung über `backend/` (behalten oder löschen)
- [ ] **H2** Entscheidung über `frontend/` (behalten oder löschen)
- [ ] **M3** CORS auf eigene Domain einschränken
- [ ] **N3** `exports/` aus Git-Tracking entfernen
