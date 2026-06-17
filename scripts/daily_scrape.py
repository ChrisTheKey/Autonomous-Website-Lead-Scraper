"""
Daily scrape scheduler — runs one search per execution, rotates through
industries and Swiss cities to find ~20 new leads per day.
Called by cron once per day.
"""

import json
import random
import sys
import urllib.request
import urllib.error
from datetime import date
from pathlib import Path

API = "http://localhost:8000"
STATE_FILE = Path(__file__).parent / "daily_scrape_state.json"

INDUSTRIES = [
    "Coiffeur", "Schreinerei", "Malerbetrieb", "Sanitär", "Elektriker",
    "Bäckerei", "Metzgerei", "Blumenladen", "Fotograf", "Reinigungsfirma",
    "Zahnarzt", "Physiotherapie", "Optiker", "Kosmetikstudio", "Gartenbau",
    "Schlüsseldienst", "Umzugsunternehmen", "Fahrschule", "Tierarzt", "Buchhalter",
    "Steuerberater", "Anwalt", "Architekt", "Innenarchitekt", "Druckerei",
    "Werbeagentur", "Fitnessstudio", "Yogastudio", "Restaurant", "Café",
    "Catering", "Eventlocation", "Hotelbetrieb", "Camping", "Kita",
]

LOCATIONS = [
    "Zürich", "Bern", "Basel", "Genf", "Lausanne",
    "Winterthur", "St. Gallen", "Luzern", "Biel", "Thun",
    "Köniz", "La Chaux-de-Fonds", "Schaffhausen", "Fribourg", "Chur",
    "Uster", "Vernier", "Sion", "Emmen", "Zug",
    "Aarau", "Solothurn", "Frenkendorf", "Baden", "Olten",
]


def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"industry_idx": 0, "location_idx": 0, "runs": []}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2))


def post_search(industry: str, location: str, max_results: int = 20) -> dict:
    payload = json.dumps({
        "industry": industry,
        "location": location,
        "max_results": max_results,
    }).encode()
    req = urllib.request.Request(
        f"{API}/search",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())


def main():
    state = load_state()
    today = date.today().isoformat()

    # Skip if already ran today
    if state.get("runs") and state["runs"][-1].get("date") == today:
        print(f"Already ran today ({today}), skipping.")
        sys.exit(0)

    i_idx = state["industry_idx"] % len(INDUSTRIES)
    l_idx = state["location_idx"] % len(LOCATIONS)
    industry = INDUSTRIES[i_idx]
    location = LOCATIONS[l_idx]

    print(f"[{today}] Scraping: {industry} in {location} (max 20)")
    try:
        result = post_search(industry, location, max_results=20)
        search_id = result.get("id")
        print(f"  → Search queued: id={search_id}, status={result.get('status')}")
        state["runs"].append({"date": today, "industry": industry, "location": location, "search_id": search_id})
        state["industry_idx"] = (i_idx + 1) % len(INDUSTRIES)
        state["location_idx"] = (l_idx + 1) % len(LOCATIONS)
        state["runs"] = state["runs"][-90:]  # keep last 90 days
        save_state(state)
    except urllib.error.URLError as e:
        print(f"  ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
