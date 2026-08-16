# DATA_STORAGE — Datenspeicherung und Datenmodelle

**Stand:** 2026-08-16 · Keine Zugangsdaten in diesem Dokument.

---

## 1. Wo Daten aktuell gespeichert werden

| Speicherort | Verwendung | Status |
|---|---|---|
| **PostgreSQL 16** | Einziger Primärspeicher beider Systeme | vorgesehen, Container in Compose definiert |
| **Redis 7** | Celery-Queues + Task-Ergebnisse; in System B zusätzlich ein Connection-Pool ohne Nutzer | vorgesehen |
| Lokale Dateien / JSON / CSV | **keine** — CSV wird nur im RAM erzeugt (`io.StringIO`) und direkt gestreamt | — |
| SQLite | **nicht vorhanden** | — |
| Supabase / Google Sheets / Airtable | **nicht vorhanden** | — |
| Vector-DB | **nicht vorhanden**; LlamaIndex-Index lebt nur im Prozessspeicher (`_index` als Modul-Global) und ist nach jedem Neustart weg | — |
| Cloud Storage / S3 | **nicht vorhanden** | — |
| CRM als Zielspeicher | HubSpot / Pipedrive / Salesforce in System B vorgesehen, nie ausgeführt | experimentell |

**Es liegen aktuell null persistierte Nutzdaten im Repository.** Kein Dump, kein Fixture,
kein Beispielexport, kein `data/`-Verzeichnis.

---

## 2. Zwei konkurrierende Datenbank-Schemata

Beide Systeme bringen eine **eigene Alembic-Historie mit der Revision `0001`** und ohne
gemeinsame Basis mit. Laufen beide gegen dieselbe Datenbank, überschreiben sie sich gegenseitig
in der Tabelle `alembic_version` — die zweite Migration hält die erste für bereits angewendet.

| | System A | System B |
|---|---|---|
| Migration | `alembic/versions/0001_initial_schema.py` | `backend/alembic/versions/0001_initial_schema.py` |
| Revision-ID | `0001` | `0001` |
| Tabellen | 7 | 2 |
| Default-DB-Name | `lead_discovery` | `lead_scraper` |
| Zentrale Entität | `companies` | `leads` |

---

## 3. Schema System A (das Produktschema)

### 3.1 Tabellenübersicht

| Tabelle | Zweck | Zeilen-Herkunft |
|---|---|---|
| `searches` | Ein Suchauftrag (Branche, Ort, Radius, Keywords, Ziel) | `POST /search` |
| `companies` | **Zentrale Lead-Entität** | Google Places, ggf. angereichert |
| `place_candidates` | Google-Rohsignal pro Treffer, mit TTL und Payload-**Hash** | pro Places-Treffer |
| `crawled_pages` | Jede gecrawlte Unterseite mit Status und Textauszug | `crawl_company_task` |
| `contacts` | Personen-/Geschäftskontakte mit Herkunftsnachweis | `extractor_service` |
| `audit_logs` | Lückenlose Aktionshistorie | jede Aktion |
| `suppression_list` | Sperrliste (Domain, Telefon, E-Mail, Place-ID) | manuelle Sperrung |

### 3.2 `companies` — wichtige Felder

**Identität:** `name`, `normalized_name` (idx), `industry`, `location`, `address`, `phone`,
`website`, `normalized_domain` (idx), `google_place_id` (**unique**, idx)

**Klassifizierung:**
- `lead_type` (idx): `no_website_candidate` | `weak_website_candidate` |
  `website_exists_not_target` | `invalid_or_risky`
- `lead_source_type`: `google_places` | `company_website` | `manual_entry` |
  `licensed_provider` | `public_register`
- `enrichment_status` (idx): `discovered` → `place_only` → `no_website` / `website_found` →
  `website_analyzed` → `manual_review_required` → `verified` / `rejected`
- `status` (idx): `discovered` | `needs_review` | `verified` | `rejected` | `contacted` | `suppressed`
- `lead_priority` (idx): `high_priority` | `medium_priority` | `low_priority` | `blocked`

**Scoring:** `website_opportunity_score` (0–100), `confidence_score` *(wird nie geschrieben)*

**Compliance:** `can_export`, `export_block_reason`, `data_origin`, `data_retention_until`,
`google_data_expires_at`, `verified_at`, `contacted_at`

**Qualitätssignale (Cache):** `has_https`, `has_mobile_viewport`, `has_contact_page`,
`website_reachable`, `weak_website_reason`

### 3.3 `contacts` — der datenschutzkritische Teil

| Feld | Bedeutung |
|---|---|
| `full_name`, `role`, `email`, `phone` | nur, was explizit auf der Seite steht |
| `source_url` | **Herkunftspflicht** — ohne diesen Wert blockiert das Gate den Export |
| `source_type` | z. B. `company_website` |
| `confidence_score` | 0.7 bei Label-Treffer, 0.8 bei generischer Firmen-E-Mail |
| `is_personal_data` | `True` bei jedem Klarnamen → erzwingt manuelle Prüfung |
| `review_status` | `needs_review` \| `verified` \| `rejected` *(kein Endpunkt setzt das je)* |

### 3.4 Beziehungen

```
searches (1) ──< companies (n)
searches (1) ──< place_candidates (n)
companies (1) ──< place_candidates (n)      [company_id nullable]
companies (1) ──< crawled_pages (n)
companies (1) ──< contacts (n)
companies (1) ──< suppression_list (n)      [company_id nullable]
audit_logs                                   [entity_type + entity_id, KEIN Foreign Key]
```

`audit_logs` ist bewusst polymorph (`entity_type`/`entity_id`) und damit ohne referenzielle
Integrität — akzeptabel für ein Log, aber ohne DB-seitige Garantie.

### 3.5 Datenschutz-Design (positiv hervorzuheben)

1. **Kein Google-Rohsatz in der DB.** `place_candidates.raw_payload_hash` speichert einen
   SHA-256-Hash statt der Antwort (`places_service.PlaceResult.payload_hash`) — konform zur
   Google-Maps-Platform-ToS.
2. **TTL auf Google-Daten.** `expires_at` / `google_data_expires_at` = Abruf + `GOOGLE_DATA_TTL_DAYS`.
3. **Herkunftspflicht für Personendaten.** Ohne `source_url` kein Export.
4. **Sperrliste mit vier Schlüsseln** (Company-ID, Place-ID, Domain, normalisiertes Telefon).
5. **Lückenlose Audit-Kette** — inklusive eines Eintrags **pro exportierter CSV-Zeile**.

⚠️ **Die Kehrseite:** Punkte 2 und die Retention (`data_retention_until`) werden **gesetzt, aber
nie ausgewertet**. Es gibt keinen Job, der abgelaufene Daten löscht oder auffrischt. Das
Löschversprechen aus dem README ist damit **nicht implementiert**, nur vorbereitet.

---

## 4. Schema System B

| Tabelle | Felder |
|---|---|
| `leads` | `company_name`, `website` (**unique**), `email`, `phone`, `address`, `city`, `country`, `latitude`, `longitude`, `description`, `status` (`new`/`enriched`/`qualified`/`synced`/`rejected`), `source_url`, **`raw_html`**, `ai_summary`, `crm_id`, `crm_source`, Zeitstempel |
| `scrape_jobs` | `lead_id` (FK), `url`, `status`, `error`, `created_at` |

**Beziehung:** `leads (1) ──< scrape_jobs (n)`

### Kritische Unterschiede zu System A

| Aspekt | System A | System B |
|---|---|---|
| Rohdaten | nur Hash | **`raw_html` bis 50.000 Zeichen pro Lead** |
| Compliance-Gate | ja | **keins** |
| Audit-Log | ja | **keins** |
| Sperrliste | ja | **keine** |
| Personendaten-Flag | ja | **keins** |
| Retention/TTL | Felder vorhanden | **nichts** |

**Folge:** Ein Lead aus System B trägt vollständiges Roh-HTML — inklusive aller darin enthaltenen
personenbezogenen Daten — unbefristet und ungeprüft in der Datenbank. Sollte System B jemals
produktiv gehen, hebelt es sämtliche Datenschutz-Zusagen aus, die System A einhält.
Vor einem Server-Umzug ist das die **wichtigste inhaltliche Entscheidung**.

---

## 5. Indizes und Performance

**Vorhanden** (`alembic/versions/0001_initial_schema.py`): `companies.lead_type`,
`companies.status`, `companies.lead_priority`, `companies.normalized_name`,
`companies.normalized_domain`, `companies.google_place_id` (unique),
`audit_logs(entity_type, entity_id)`, diverse Fremdschlüssel-Indizes.

**Fehlend / auffällig:**
- Kein Index auf `companies.website_opportunity_score`, obwohl `GET /companies` **immer**
  danach sortiert (`ORDER BY website_opportunity_score DESC`) → Full-Table-Sort ab einigen
  10.000 Zeilen.
- Kein Index auf `companies.phone`, obwohl `dedupe_service.find_duplicate` danach sucht.
- Kein Index auf `contacts.is_personal_data`, obwohl das Gate bei **jeder** Export-Bewertung
  darüber filtert.
- Kein zusammengesetzter Index für den Export-Filter `(status, can_export)`.
- `crawled_pages.text_excerpt` (bis 2.000 Zeichen/Seite × 10 Seiten × n Firmen) ist der
  Haupttreiber des Speicherwachstums in System A; in System B ist es `leads.raw_html`.

---

## 6. Verbindungs- und Transaktionsverhalten

| Aspekt | System A | System B |
|---|---|---|
| Pooling | `pool_size=10`, `max_overflow=20`, `pool_pre_ping=True` | **keine Pool-Parameter** (SQLAlchemy-Defaults) |
| Session-Handling | `get_db()` mit commit/rollback-Wrapper | `get_db()` **ohne** Rollback-Behandlung |
| Worker-Sessions | eigene `AsyncSessionLocal()` pro Task | dito |
| Bridging | `asyncio.run()` in jedem Celery-Task | dito |

**Kapazitätshinweis für die Serverdimensionierung:** Bei 3 Celery-Workern (2+4+4 = 10 Prozesse)
plus API entstehen im Worst Case rund 10 × (10+20) + 30 ≈ **330 mögliche DB-Verbindungen**.
PostgreSQL steht per Default auf `max_connections = 100`. Ohne PgBouncer oder reduzierte
Pool-Grössen läuft der Stack unter Last in „too many connections". Das ist vor einer
Server-Bestellung einzuplanen.
