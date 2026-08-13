# SYSTEM OVERVIEW — Autonomous Website Lead Scraper

**Stand:** August 2026  
**Zielmarkt:** Deutschschweiz (B2B, KMU ohne / mit schwachem Website)  
**Zweck:** Findet Schweizer KMU ohne professionellen Webauftritt → qualifiziert sie als Leads → exportiert sie für Outreach

---

## Was dieses System tut

Das System ist ein **B2B Lead Discovery Service** für Webdesign-Agenturen (primär Helvetic Webdesign). Es:

1. **Sucht** Schweizer Kleinunternehmen via Google Places API
2. **Klassifiziert** jeden Treffer: kein Website / social-only / schwacher Baukasten / professionell
3. **Bewertet** Leads mit einem Opportunity Score (0–100) — je schlechter der Webauftritt, desto höher
4. **Crawlt** Websites um E-Mail-Adressen und Inhabernamen zu extrahieren (via Claude AI)
5. **Exportiert** qualifizierte Leads als Excel/CSV für Telefon-Outreach

---

## Zwei Modi

### Modus A: Vollstack (FastAPI + PostgreSQL + Celery)
Für dauerhaften Betrieb auf einem Server. Suchen werden über `/search` API getriggert, Celery übernimmt asynchrone Verarbeitung.

### Modus B: Standalone-Skripte (direkt ausführbar)
Für schnelle Einzel-Scrapes ohne laufende Infrastruktur. Braucht nur `GOOGLE_MAPS_API_KEY` + `ANTHROPIC_API_KEY`.

**Aktuell in Betrieb:** Modus B via `scripts/bern_innendekorateure.py`

---

## End-to-End Workflow

```
Input (Branche + Region)
        ↓
Google Places API (searchText)
        ↓
Klassifikation (kein/social/schwach/ok Website)
        ↓
Opportunity Scoring (0–100, deterministisch)
        ↓
Website Crawling (httpx → Kontakt-/Impressumsseite)
        ↓
Claude AI (claude-opus-4-8) → Inhabername + Rolle
        ↓
E-Mail Extraktion (Regex, validiert)
        ↓
Excel Export (3 Sheets: Leads, Scoring-Modell, Statistik)
        ↓
Output: bern_innendekorateure.xlsx
```

---

## Systemkomponenten

| Komponente | Status | Beschreibung |
|---|---|---|
| Google Places Scraping | ✅ Funktioniert | 8 Queries × 20 Ergebnisse, Deduplizierung |
| Website-Klassifikation | ✅ Funktioniert | Social/Weak/None/OK korrekt erkannt |
| Opportunity Scoring | ✅ Funktioniert | Deterministisch, 0–100 |
| Claude-basierte Namenextraktion | ✅ Funktioniert | Echte Inhabernamen, validiert |
| E-Mail Extraktion | ✅ Funktioniert | Regex + Skip-Liste für Junk-Adressen |
| Excel Export | ✅ Funktioniert | 3-Sheet Workbook, professionell formatiert |
| FastAPI REST-API | ⚠️ Vorhanden, nicht aktiv | Braucht PostgreSQL + Redis |
| Celery Task Queue | ⚠️ Vorhanden, nicht aktiv | Braucht Redis |
| PostgreSQL Persistenz | ⚠️ Vorhanden, nicht aktiv | Braucht laufende DB |
| CRM-Integration | 🔵 Konfigurierbar | HubSpot/Salesforce/Pipedrive (keys optional) |
| Outreach-Agent | 🔵 Vorbereitet | Companion-Repo erwartet leads.csv |
| backend/ Stack | 🧪 Experimentell | LangChain, Scrapy, Airflow, Temporal |
| frontend/ Next.js | 🧪 Experimentell | Nicht funktionsfähig |

---

## Letzter produzierter Output

`exports/bern_innendekorateure.xlsx` (August 2026):
- 64 echte Betriebe (Innendekorateure, Innenarchitekten, Raumausstatter)
- 61 mit Telefonnummer (95%)
- 12 mit E-Mail (18%)
- 10 mit Inhabername (15%)
- Alle aus Grossraum Bern (15 km Radius)

---

## Technischer Stack

| Schicht | Technologie |
|---|---|
| Sprache | Python 3.11 |
| API Framework | FastAPI + Uvicorn |
| ORM | SQLAlchemy 2.0 (async) |
| Datenbank | PostgreSQL 16 (asyncpg) |
| Task Queue | Celery 5 + Redis 7 |
| AI | Claude claude-opus-4-8 (Anthropic SDK) |
| HTTP | httpx (async) |
| Browser | Playwright (Chromium, für JS-Seiten) |
| Export | openpyxl (Excel), csv (stdlib) |
| Containerisierung | Docker + Docker Compose |
| Deployment | Systemd Services |
| Tests | pytest + pytest-asyncio |

---

## Compliance-Architektur

Das System hat mehrere eingebaute Compliance-Massnahmen für revDSG (Schweiz) / DSGVO:

- Google-Rohdaten werden **nie gespeichert** — nur SHA-256 Hash
- Daten haben ein konfigurierbares TTL (`GOOGLE_DATA_TTL_DAYS`, Default 30)
- Nur Geschäftsdaten, keine Privatadressen
- Crawler identifiziert sich ehrlich (`LeadDiscoveryBot/1.0`)
- Crawler respektiert `robots.txt`
- Export-Gate: nur `verified` + `can_export=True` Leads exportierbar
- Unveränderliches Audit-Log für jede Statusänderung
- DSGVO-Sperrliste (`suppression_list` Tabelle)
- Rechtsgrundlage: Berechtigtes Interesse B2B (Art. 31 revDSG / Art. 6 Abs. 1 lit. f DSGVO)
