# DATA STORAGE — Datenspeicherung und Datenmodelle

**Stand:** August 2026

---

## Aktueller Speicherstatus

| Was | Wo | Format | Status |
|---|---|---|---|
| Lead-Daten (Vollstack) | PostgreSQL 16 | Relationale DB | ⚠️ Nur aktiv wenn Docker/Server läuft |
| Excel-Exports | `exports/*.xlsx` | openpyxl | ✅ Vorhanden (bern_innendekorateure.xlsx) |
| CSV-Exports | `exports/*.csv` | Python csv | ✅ Vorhanden (bern_innendekorateure.csv) |
| Outreach-Export | `~/Autonomer-Website-Outreach-Agent/data/leads.csv` | CSV | ⚠️ Nur bei konfiguriertem Companion-Repo |
| Scraper-State | `scripts/daily_scrape_state.json` | JSON | ⚠️ Existiert nur nach erstem daily_scrape-Run |
| Logs | `logs/daily_pipeline.log` | Plaintext | ⚠️ Nur wenn daily_pipeline.sh läuft |

---

## PostgreSQL Datenbankschema (Vollstack-Modus)

### Tabelle: `searches`
```sql
id              SERIAL PRIMARY KEY
industry        VARCHAR NOT NULL
location        VARCHAR NOT NULL
radius_km       FLOAT DEFAULT 10.0
keywords        JSONB DEFAULT '[]'
status          ENUM(queued, running, completed, failed)
target          INTEGER DEFAULT 10
result_count    INTEGER DEFAULT 0
created_at      TIMESTAMP DEFAULT NOW()
completed_at    TIMESTAMP
```
**Zweck:** Protokoll aller Suchanfragen

### Tabelle: `companies` (Kern-Entität)
```sql
id                        SERIAL PRIMARY KEY
google_place_id           VARCHAR UNIQUE          -- Google Places ID
name                      VARCHAR NOT NULL
industry                  VARCHAR
location                  VARCHAR
address                   VARCHAR
phone                     VARCHAR
website                   VARCHAR
email                     VARCHAR

-- Lead-Klassifikation
lead_type                 ENUM(no_website_candidate, weak_website_candidate,
                               website_exists_not_target, invalid_or_risky)
lead_source               ENUM(google_places, manual, import)
lead_priority             ENUM(high_priority, medium_priority, low_priority)
status                    ENUM(discovered, needs_review, verified, rejected,
                               contacted, suppressed)
can_export                BOOLEAN DEFAULT FALSE

-- Scoring
website_opportunity_score INTEGER (0-100)    -- deterministisch
ai_opportunity_score      INTEGER (0-100)    -- via Claude
ai_analysis               TEXT               -- Claude-Begründung

-- Timestamps
created_at                TIMESTAMP
verified_at               TIMESTAMP
contacted_at              TIMESTAMP
rejected_at               TIMESTAMP
```

### Tabelle: `contacts`
```sql
id                INTEGER PRIMARY KEY
company_id        INTEGER FK → companies.id
full_name         VARCHAR                    -- Inhabername
role              VARCHAR                    -- z.B. "Inhaberin"
email             VARCHAR
phone             VARCHAR
source_url        VARCHAR                    -- Pflicht wenn is_personal_data=True
is_personal_data  BOOLEAN DEFAULT TRUE
review_status     ENUM(pending, approved, rejected)
created_at        TIMESTAMP
```

### Tabelle: `place_candidates`
```sql
id                INTEGER PRIMARY KEY
company_id        INTEGER FK → companies.id
google_place_id   VARCHAR
has_website       BOOLEAN
raw_payload_hash  VARCHAR(64)               -- SHA-256, kein Klartext!
types             JSONB
expires_at        TIMESTAMP                  -- TTL via GOOGLE_DATA_TTL_DAYS
```

### Tabelle: `crawled_pages`
```sql
id              INTEGER PRIMARY KEY
company_id      INTEGER FK → companies.id
url             VARCHAR
status_code     INTEGER
title           VARCHAR
text_excerpt    TEXT (max 2000 Zeichen)
robots_allowed  BOOLEAN
crawled_at      TIMESTAMP
```

### Tabelle: `audit_logs`
```sql
id              INTEGER PRIMARY KEY
entity_type     VARCHAR    -- 'company', 'contact', 'export'
entity_id       INTEGER
action          VARCHAR    -- 'status_changed', 'exported', 'ai_analysed'
actor           VARCHAR    -- 'system', 'api', 'worker'
extra           JSONB      -- Details der Aktion
created_at      TIMESTAMP
```

### Tabelle: `suppression_list`
```sql
id              INTEGER PRIMARY KEY
company_id      INTEGER FK → companies.id (nullable)
domain          VARCHAR
phone           VARCHAR
email           VARCHAR
google_place_id VARCHAR
reason          VARCHAR
created_at      TIMESTAMP
```

---

## Aktueller Output-Export (bern_innendekorateure.xlsx)

```
Sheet 1: "Bern Innendekorateure" (Haupt-Leads)
  Spalten: Nr | Branche | Firmenname | Vorname Inhaber | Nachname Inhaber |
           Telefon | E-Mail | Website | Website-Status | Opp. Score |
           Adresse | Google Bewertung

Sheet 2: "Scoring-Modell"
  Erklärung der Score-Berechnung für den Nutzer

Sheet 3: "Statistiken & Branchen"
  Kennzahlen: Gesamt, Mit Telefon, Mit E-Mail, Mit Inhabername
  Branchen-Verteilung
```

---

## Was NICHT gespeichert wird

| Was | Warum |
|---|---|
| Google Places Rohdaten | Google ToS + Compliance: nur SHA-256 Hash |
| Vollständige Website-HTMLs | Nur `text_excerpt` (max 2000 Zeichen) |
| Passwörter / API-Keys | Nur in .env, nie in DB oder Repo |
| Private Personendaten | Nur öffentliche Geschäftsdaten |

---

## Für Server-Betrieb benötigte Persistenz

```bash
# PostgreSQL (automatisch via Docker Compose)
docker volume: postgres_data

# Redis (automatisch via Docker Compose)
docker volume: redis_data

# Exports (als Volume mounten für Persistenz)
/opt/lead-scraper/exports/ → /mnt/storage/lead-scraper/exports/

# .env mit API-Keys
/opt/lead-scraper/.env (chmod 600)
```
