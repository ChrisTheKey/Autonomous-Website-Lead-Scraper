# ARCHITECTURE — End-to-End Datenfluss

**Stand:** August 2026

---

## Kompaktübersicht

```
INPUT                    VERARBEITUNG                      OUTPUT
──────                   ────────────                      ──────
Branche + Region    →    Google Places API             →   Rohe Betriebsdaten
                    →    Klassifikation (LeadType)      →   no/social/weak/ok
                    →    Opportunity Scoring            →   Score 0–100
                    →    Website Crawling               →   HTML-Text
                    →    Claude AI (claude-opus-4-8)    →   Inhabername + Rolle
                    →    Regex                          →   E-Mail
                    →    openpyxl                       →   Excel-Datei
```

---

## Schritt-für-Schritt: Ein Lead durch das System

### Beispiel-Input
```
Branche:   "Innendekorateur"
Region:    "Bern"
Radius:    15 km
```

### Schritt 1 — Google Places API (places_service.py)
```
POST https://places.googleapis.com/v1/places:searchText
Body: { "textQuery": "Innendekorateur Bern", "locationBias": { ... 15km ... } }
Header: X-Goog-Api-Key: [GOOGLE_MAPS_API_KEY]

Response → place_id, displayName, phone, websiteUri, rating, userRatingCount, address
```
→ 20 Ergebnisse pro Query, 8 Queries = bis zu 160 Rohtreffer

### Schritt 2 — Deduplizierung (dedupe_service.py)
```python
seen_ids = set()
for place in all_places:
    if place["id"] not in seen_ids:
        seen_ids.add(place["id"])
        # → Weitergabe
```
→ 64 einzigartige Betriebe

### Schritt 3 — Website-Klassifikation (website_detection_service.py)
```python
def classify_website(url: str) -> str:
    if not url:           return "none"    # Kein Website
    if in SOCIAL_DOMAINS: return "social"  # Facebook, Instagram, TikTok etc.
    if in WEAK_BUILDERS:  return "weak"    # Wix, Jimdo, WordPress.com etc.
    return "ok"                            # Eigene Domain → kein Bedarf
```

### Schritt 4 — Opportunity Scoring (scoring_service.py)
```python
base = {"none": 65, "social": 58, "weak": 52, "ok": 20}[ws_class]
if phone:          base += 12   # Direktkontakt möglich
if reviews >= 20:  base += 8    # Etabliertes Unternehmen
if reviews >= 5:   base += 4
score = min(100, base)
```

### Schritt 5 — Website Crawling (contact_extractor.py)
```
Seiten: /, /kontakt, /contact, /ueber-uns, /about, /team
HTTP GET via httpx (SSL-tolerant, follow_redirects=True)
Max 80'000 Bytes pro Seite
```

### Schritt 6 — E-Mail Extraktion (contact_extractor.py)
```python
EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
# Skip: noreply, example, test@, sentry, placeholder
```

### Schritt 7 — Inhabername via Claude (contact_extractor.py → ai_service)
```
Input an Claude claude-opus-4-8:
  - Firmenname
  - Website-Plaintext (bis 4000 Zeichen, HTML entfernt)

Prompt:
  "Finde den echten Inhaber, Geschäftsführer oder Hauptansprechpartner.
   Nur ECHTE Personennamen — keine Firmennamen, keine Navigationselemente.
   Antwort als JSON: {vorname, nachname, rolle}"

Validierung nach Rückkehr:
  - Junk-Filter: {"ag", "gmbh", "bern", "kontakt", "impressum", ...}
  - Länge: vorname und nachname jeweils > 1 Zeichen
```

### Schritt 8 — Excel Export (build_excel in bern_innendekorateure.py)
```
Sheet 1: Leads (Nr, Branche, Firma, Vorname, Nachname, Telefon, E-Mail, Website, Score, Adresse, Anrufzeit)
Sheet 2: Scoring-Modell (Erklärung der Score-Berechnung)
Sheet 3: Statistiken (Kennzahlen, Branchen-Verteilung)
```

### Output
```
Datei: exports/bern_innendekorateure.xlsx
Grösse: ~19 KB
Inhalt: 64 Leads, 61 mit Telefon, 12 mit E-Mail, 10 mit Inhabername
```

---

## Vollstack-Modus (FastAPI + Celery) — wenn aktiviert

```
POST /search { "industry": "Coiffeur", "location": "Zürich", "max_results": 10 }
        ↓
searches.py → erstellt Search-Record in PostgreSQL (status: queued)
        ↓
BackgroundTasks.add_task(_dispatch_search, search_id)
        ↓
Celery Task: run_search_task(search_id) → Queue: search
        ↓
search_orchestrator.run_search()
  → places_service.search_places()        [Google Places API]
  → website_detection_service.classify()
  → dedupe_service.deduplicate()
  → scoring_service.score()
  → DB: INSERT companies, place_candidates
  → compliance_service.write_audit_log()
  ↓
Celery Chain: crawl_company_task(id) → analyse_website_task(id)
  → crawler_service.crawl()               [httpx / Playwright]
  → extractor_service.extract()
  → website_quality_service.analyse()
  → DB: UPDATE companies, INSERT contacts, crawled_pages
        ↓
GET /companies → gefilterte Lead-Liste
        ↓
POST /companies/{id}/ai-analyse
  → ai_service.analyse_company()          [Claude API]
  → DB: UPDATE company.ai_analysis
        ↓
POST /companies/{id}/verify → status: verified, can_export: True
        ↓
GET /export/csv → compliance_service.check() → export_service.export()
        ↓
export_leads.py → ~/Autonomer-Website-Outreach-Agent/data/leads.csv
```

---

## Datenbankschema (PostgreSQL)

```
searches
  id, industry, location, radius_km, keywords (JSONB), status, target, created_at

companies
  id, name, industry, location, phone, website, google_place_id (UNIQUE)
  lead_type (ENUM), status (ENUM), lead_priority (ENUM)
  website_opportunity_score (0-100), can_export (BOOL)
  verified_at, contacted_at, rejected_at
  ai_opportunity_score, ai_analysis (TEXT)

contacts
  id, company_id (FK), full_name, role, email, phone
  is_personal_data (BOOL), review_status, source_url

place_candidates
  id, company_id (FK), google_place_id, has_website
  raw_payload_hash (SHA256), expires_at

crawled_pages
  id, company_id (FK), url, status_code, title
  text_excerpt, robots_allowed

audit_logs
  id, entity_type, entity_id, action, actor, extra (JSONB), created_at

suppression_list
  id, company_id, domain, phone, email, google_place_id, reason, created_at
```

---

## Companion-System: Outreach-Agent

Separates Repository `~/Autonomer-Website-Outreach-Agent/` liest:
- `data/leads.csv` — von `export_leads.py` generiert
- `data/new_leads_ready.json` — Trigger-Datei von `scripts/daily_pipeline.sh`

Kommunikation zwischen den Systemen: **Dateisystem** (kein API, kein Event-Bus).  
Dies ist ein **Single Point of Failure** — wenn das Verzeichnis fehlt, schlägt der Export stumm fehl.

---

## Nicht verbundene Teile (Stand August 2026)

| Was | Warum getrennt |
|---|---|
| `backend/` Parallelstack | Experimentell, anderer Tech-Stack (LangChain, Scrapy, Airflow) |
| `frontend/` Next.js | Nie in Betrieb genommen, kein Backend-Binding |
| Vollstack-Modus | Braucht PostgreSQL + Redis (nicht auf Remote-Session verfügbar) |
| CRM-Integration | Keys optional, nie getestet in Produktion |
| Outreach-Agent | Separates Repo, hartkodierter Pfad `/home/chris/...` |
| Webhook-Endpoints | In-Memory-Speicherung (geht verloren bei Neustart) |
