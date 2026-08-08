"""
Trigger 100 leads across 10 industries, wait for enrichment, export prioritised CSV.
Run: python scripts/build_100_leads.py
"""

import asyncio
import csv
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

API = "http://localhost:8000"
OUT = Path(__file__).parent.parent / "exports" / "100_leads_priorisiert.csv"

# 10 Branchen × 10 Leads = 100 total, Region Deutschschweiz
SEARCHES = [
    ("Gastronomie",        "Zürich"),
    ("Handwerk",           "Bern"),
    ("Fitness Wellness",   "Basel"),
    ("Immobilien Makler",  "Winterthur"),
    ("Coaching Beratung",  "Luzern"),
    ("Zahnarzt",           "St. Gallen"),
    ("Physiotherapie",     "Aarau"),
    ("Fotograf",           "Zug"),
    ("Coiffeur",           "Thun"),
    ("Autowerkstatt",      "Solothurn"),
]

FIELDS = [
    "lead_id", "firma", "branche", "region", "telefon", "email",
    "website", "quelle", "opportunity_score", "score_begruendung",
    "rechtsgrundlage",
]

SCORE_WEIGHTS = {
    "no_website":              60,   # Kein Website → höchster Bedarf
    "weak_website_candidate":  35,   # Schwache Website → guter Bedarf
    "website_exists_not_target": 10, # Hat Website → geringer Bedarf
    "invalid_or_risky":         0,
    None:                       20,
}

PRIORITY_BONUS = {"high_priority": 30, "medium_priority": 15, "low_priority": 0, None: 0}


def post(path: str, body: dict) -> dict:
    data = json.dumps(body).encode()
    req = urllib.request.Request(f"{API}{path}", data=data,
                                  headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())


def get(path: str) -> dict | list:
    with urllib.request.urlopen(f"{API}{path}", timeout=15) as r:
        return json.loads(r.read())


def score_lead(company: dict) -> tuple[int, str]:
    base = SCORE_WEIGHTS.get(company.get("lead_type"), 20)
    bonus = PRIORITY_BONUS.get(company.get("lead_priority"), 0)
    has_phone = 10 if company.get("phone") else 0
    has_email = 15 if company.get("email") else 0
    score = min(100, base + bonus + has_phone + has_email)

    reasons = []
    lt = company.get("lead_type", "")
    if lt == "no_website":
        reasons.append("Kein Website (hoher Bedarf)")
    elif lt == "weak_website_candidate":
        reasons.append("Schwache Website (Optimierungsbedarf)")
    elif lt == "website_exists_not_target":
        reasons.append("Website vorhanden (geringer Bedarf)")
    if company.get("lead_priority") == "high_priority":
        reasons.append("hohe Priorität")
    if company.get("phone"):
        reasons.append("Telefon verfügbar")
    return score, "; ".join(reasons) if reasons else "Standardbewertung"


def main():
    print("=" * 60)
    print("Build 100 Leads — 10 Branchen × 10 Leads")
    print("=" * 60)

    # Step 1: Trigger searches
    search_ids = []
    for industry, location in SEARCHES:
        result = post("/search", {"industry": industry, "location": location, "max_results": 10})
        search_ids.append(result["id"])
        print(f"  ✓ Search {result['id']:>3}: {industry} in {location}")
        time.sleep(2)  # small delay to avoid flooding

    print(f"\nTriggered {len(search_ids)} searches. Waiting 4 min for enrichment...")
    time.sleep(240)

    # Step 2: Fetch all companies
    print("Fetching companies from API...")
    companies = get("/companies?limit=200")
    print(f"  → {len(companies)} companies in DB")

    # Step 3: Fetch contacts for email lookup
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from app.models.contact import Contact

    async def get_contacts():
        db_url = os.getenv("DATABASE_URL", "")
        engine = create_async_engine(db_url, echo=False)
        Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with Session() as db:
            result = await db.execute(select(Contact))
            contacts = result.scalars().all()
            data = {c.company_id: c for c in contacts if c.company_id}
        await engine.dispose()
        return data

    contacts = asyncio.run(get_contacts())

    # Step 4: Score and sort
    rows = []
    for c in companies:
        contact = contacts.get(c["id"])
        opp_score, reason = score_lead(c)
        rows.append({
            "lead_id":             c["id"],
            "firma":               c.get("name", ""),
            "branche":             c.get("industry", ""),
            "region":              c.get("location", ""),
            "telefon":             c.get("phone", ""),
            "email":               (contact.email if contact else "") or "",
            "website":             c.get("website", ""),
            "quelle":              "Google Places API (öffentliche Geschäftsdaten)",
            "opportunity_score":   opp_score,
            "score_begruendung":   reason,
            "rechtsgrundlage":     "Berechtigtes Interesse (B2B, revDSG Art. 31 / CH)",
        })

    rows.sort(key=lambda r: r["opportunity_score"], reverse=True)
    rows = rows[:100]

    # Step 5: Export CSV
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n✓ Exported {len(rows)} leads → {OUT}")
    print("\nTop 5 nach Opportunity-Score:")
    for r in rows[:5]:
        print(f"  [{r['opportunity_score']:>3}] {r['firma'][:40]:<40} {r['branche']}")

    print("\n--- Scoring-Modell ---")
    print("  Kein Website:              60 Punkte (höchster Webdesign-Bedarf)")
    print("  Schwache Website:          35 Punkte (Redesign-Potenzial)")
    print("  Website vorhanden:         10 Punkte (geringer Bedarf)")
    print("  Hohe Priorität (intern):  +30 Punkte")
    print("  Mittlere Priorität:       +15 Punkte")
    print("  Telefonnummer vorhanden:  +10 Punkte")
    print("  E-Mail vorhanden:         +15 Punkte")
    print("  Maximum:                  100 Punkte")
    print("\n--- Rechtsgrundlage ---")
    print("  Quelle: Google Places API (öffentliche Gewerbedaten)")
    print("  Basis:  Berechtigtes Interesse B2B (revDSG Art. 31 / DSGVO Art. 6 Abs. 1 lit. f)")
    print("  Nur Geschäftskontakte, keine Privatpersonen")


if __name__ == "__main__":
    main()
