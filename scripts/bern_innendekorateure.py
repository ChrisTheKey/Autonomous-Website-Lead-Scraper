"""
Bern — Innendekorateure / Innenarchitekten
===========================================
Google Places API → alle Treffer in Bern
Claude API        → Inhaber-Name (aus HTML extrahiert, kein Regex-Raten)
Regex             → E-Mail (zuverlässig per Pattern)
Export            → Excel + CSV

Ausführen:
    cd ~/Autonomous-Website-Lead-Scraper
    source venv/bin/activate
    python scripts/bern_innendekorateure.py
"""

import asyncio
import csv
import json
import re
import ssl
import sys
import time
import urllib.request
import urllib.parse
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

import os
GOOGLE_KEY    = os.getenv("GOOGLE_MAPS_API_KEY", "")
ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY", "")
if not GOOGLE_KEY:
    print("FEHLER: GOOGLE_MAPS_API_KEY fehlt in .env")
    sys.exit(1)
if not ANTHROPIC_KEY:
    print("WARNUNG: ANTHROPIC_API_KEY fehlt — Inhabernamen werden nicht extrahiert")

try:
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "openpyxl", "-q"])
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter

OUT_XLSX = Path(__file__).parent.parent / "exports" / "bern_innendekorateure.xlsx"
OUT_CSV  = Path(__file__).parent.parent / "exports" / "bern_innendekorateure.csv"

BERN_LAT, BERN_LNG = 46.9480, 7.4474
RADIUS_M = 15_000  # 15 km — ganzer Grossraum Bern

# Alle relevanten Suchbegriffe (mehrere Läufe für maximale Abdeckung)
QUERIES = [
    "Innendekorateur Bern",
    "Innenarchitekt Bern",
    "Raumausstatter Bern",
    "Inneneinrichtung Bern",
    "Interior Design Bern",
    "Vorhang Polster Bern",
    "Bodenbelag Raumgestaltung Bern",
    "Einrichtungsberatung Bern",
]

SOCIAL_DOMAINS = {
    "facebook.com","fb.com","instagram.com","twitter.com","x.com",
    "linkedin.com","xing.com","youtube.com","tiktok.com","google.com",
    "local.ch","search.ch","tripadvisor.com","yelp.com",
}
WEAK_BUILDERS = {
    "wix.com","wixsite.com","jimdo.com","jimdofree.com","weebly.com",
    "squarespace.com","wordpress.com","blogspot.com","webnode.com",
    "strikingly.com","one.com","site123.com","hostpoint.ch",
}

def classify_website(url: str) -> str:
    if not url: return "none"
    try: domain = urllib.parse.urlparse(url.lower()).netloc.lstrip("www.")
    except: return "ok"
    for s in SOCIAL_DOMAINS:
        if domain == s or domain.endswith("."+s): return "social"
    for w in WEAK_BUILDERS:
        if domain == w or domain.endswith("."+w): return "weak"
    return "ok"

def opportunity_score(ws_class, phone, reviews=0):
    base = {"none":65,"social":58,"weak":52,"ok":20}.get(ws_class,20)
    if phone:   base += 12
    if reviews >= 20: base += 8
    elif reviews >= 5: base += 4
    return min(100, base)

# ── Google Places API ────────────────────────────────────────────────────────
def places_search(query: str) -> list[dict]:
    """Holt alle Seiten der Google Places searchText API."""
    url = "https://places.googleapis.com/v1/places:searchText"
    fields = (
        "places.id,places.displayName,places.formattedAddress,"
        "places.internationalPhoneNumber,places.websiteUri,"
        "places.rating,places.userRatingCount,"
        "places.regularOpeningHours"
    )
    all_places = []
    page_token = None

    while True:
        body = {
            "textQuery": query,
            "languageCode": "de",
            "locationBias": {
                "circle": {
                    "center": {"latitude": BERN_LAT, "longitude": BERN_LNG},
                    "radius": RADIUS_M,
                }
            },
            "maxResultCount": 20,
        }
        if page_token:
            body["pageToken"] = page_token

        data = json.dumps(body).encode()
        req  = urllib.request.Request(url, data=data, headers={
            "Content-Type":   "application/json",
            "X-Goog-Api-Key": GOOGLE_KEY,
            "X-Goog-FieldMask": fields,
        })
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                resp = json.loads(r.read())
        except Exception as e:
            print(f"    Places-API Fehler: {e}")
            break

        all_places.extend(resp.get("places", []))
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
        time.sleep(1.5)

    return all_places

# ── Kontaktextraktion via Claude ─────────────────────────────────────────────
async def extract_contact_claude(url: str, company_name: str) -> tuple[str,str,str,str]:
    """
    Gibt (email, vorname, nachname, rolle) zurück.
    Claude liest den Website-Text und extrahiert den echten Inhabernamen.
    """
    from app.services.contact_extractor import extract_contact
    result = await extract_contact(
        url=url,
        company_name=company_name,
        anthropic_api_key=ANTHROPIC_KEY,
    )
    return result.email, result.vorname, result.nachname, result.rolle

# ── Excel-Export ─────────────────────────────────────────────────────────────
def _side(c="BDD7EE"): return Side(style="thin",color=c)
def _border(): s=_side(); return Border(left=s,right=s,top=s,bottom=s)
def _fill(hex): return PatternFill("solid",fgColor=hex)
def _cw(ws,col,w): ws.column_dimensions[get_column_letter(col)].width=w

DARK="0D2E4E"; MED="1A3C5E"; LIGHT="EBF3FB"

def build_excel(leads: list[dict], path: Path):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Bern Innendekorateure"
    ws.sheet_view.showGridLines = False

    # Banner
    ws.merge_cells("A1:K1")
    c=ws["A1"]; c.value="BERN — INNENDEKORATEURE & INNENARCHITEKTEN  |  Telefon · Inhaber · E-Mail  |  Helvetic Webdesign 2026"
    c.font=Font(bold=True,color="FFFFFF",size=12); c.fill=_fill(DARK)
    c.alignment=Alignment(horizontal="center",vertical="center"); ws.row_dimensions[1].height=28

    ws.merge_cells("A2:K2")
    c=ws["A2"]; c.value="✅  Echte Daten — Google Places API (Grossraum Bern 15 km)  |  Quelle: öffentliche Gewerbedaten  |  revDSG Art. 31 (B2B, berechtigtes Interesse)"
    c.font=Font(italic=True,color="FFFFFF",size=9); c.fill=_fill(MED)
    c.alignment=Alignment(horizontal="center",vertical="center"); ws.row_dimensions[2].height=16

    HDRS=[("Nr.",4),("Firmenname",30),("Vorname Inhaber",16),("Nachname Inhaber",18),
          ("Telefon",18),("E-Mail",32),("Website",34),("Website-Status",16),
          ("Opp. Score",10),("Adresse",34),("Google Bewertung",14)]
    for ci,(h,w) in enumerate(HDRS,1):
        c=ws.cell(row=3,column=ci,value=h)
        c.font=Font(bold=True,color="FFFFFF",size=10); c.fill=_fill(MED)
        c.border=_border(); c.alignment=Alignment(horizontal="center",vertical="center",wrap_text=True)
        _cw(ws,ci,w)
    ws.row_dimensions[3].height=32

    WS_LBL={"none":"Kein Website","social":"Nur Social Media","weak":"Schwache Website","ok":"Website vorhanden"}
    for ri,lead in enumerate(leads,4):
        alt=_fill(LIGHT) if ri%2==0 else PatternFill()
        sc=lead["score"]
        sc_font = Font(bold=True,color="155724") if sc>=75 else (Font(bold=True,color="7D4E00") if sc>=60 else Font(color="555555"))
        sc_fill = _fill("D4EDDA") if sc>=75 else (_fill("FFF3CD") if sc>=60 else PatternFill())
        vals=[ri-3,lead["name"],lead["vorname"],lead["nachname"],lead["phone"],
              lead["email"],lead["website"],WS_LBL.get(lead["ws_class"],"-"),
              sc,lead["address"],lead["rating"]]
        for ci,val in enumerate(vals,1):
            c=ws.cell(row=ri,column=ci,value=val)
            c.border=_border()
            c.alignment=Alignment(vertical="center",wrap_text=(ci in (2,6,7,10)),
                                   horizontal="center" if ci in (1,9,11) else "left")
            if ci==9: c.font=sc_font; c.fill=sc_fill
            else: c.fill=alt
        ws.row_dimensions[ri].height=22

    ws.freeze_panes="A4"; ws.auto_filter.ref=f"A3:K{3+len(leads)}"

    # Legende
    lr=4+len(leads)+1
    ws.merge_cells(f"A{lr}:K{lr}")
    c=ws[f"A{lr}"]; c.value="Score: 🟢 ≥75 Sehr hoch (kein/social Website + Telefon)  |  🟡 60–74 Hoch (schwaches Website)  |  Weiss <60 Mittel"
    c.font=Font(italic=True,color="666666",size=9); ws.row_dimensions[lr].height=16

    # Sheet 2: CSV-Vorschau
    ws2=wb.create_sheet("Rohdaten CSV")
    hdrs2=["Nr","Firmenname","Vorname","Nachname","Telefon","Email","Website","Score","Adresse"]
    for ci,h in enumerate(hdrs2,1):
        c=ws2.cell(row=1,column=ci,value=h)
        c.font=Font(bold=True,color="FFFFFF"); c.fill=_fill(MED); c.border=_border()
        _cw(ws2,ci,[4,28,14,16,18,32,34,8,34][ci-1])
    for ri,lead in enumerate(leads,2):
        for ci,val in enumerate([ri-1,lead["name"],lead["vorname"],lead["nachname"],
                                  lead["phone"],lead["email"],lead["website"],
                                  lead["score"],lead["address"]],1):
            c=ws2.cell(row=ri,column=ci,value=val)
            c.border=_border(); c.fill=_fill(LIGHT) if ri%2==0 else PatternFill()

    wb.properties.title="Bern Innendekorateure – Kontaktdaten"
    wb.properties.created=datetime.utcnow()
    path.parent.mkdir(parents=True,exist_ok=True)
    wb.save(path)
    print(f"✓ Excel: {path}")

def build_csv(leads: list[dict], path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=[
            "nr","firma","vorname","nachname","telefon","email",
            "website","website_status","opportunity_score","adresse","bewertung"
        ])
        w.writeheader()
        for i,lead in enumerate(leads,1):
            w.writerow({
                "nr": i, "firma": lead["name"], "vorname": lead["vorname"],
                "nachname": lead["nachname"], "telefon": lead["phone"],
                "email": lead["email"], "website": lead["website"],
                "website_status": lead["ws_class"],
                "opportunity_score": lead["score"],
                "adresse": lead["address"], "bewertung": lead["rating"],
            })
    print(f"✓ CSV:   {path}")

# ── Hauptprogramm ─────────────────────────────────────────────────────────────
async def main():
    print("="*65)
    print("Bern — Innendekorateure & Innenarchitekten")
    print("="*65)

    # Phase 1: Places API — alle Queries
    print(f"\nPHASE 1: Google Places API ({len(QUERIES)} Suchanfragen) …")
    all_places: dict[str,dict] = {}  # place_id → place
    for q in QUERIES:
        print(f"  Suche: {q} …", end="", flush=True)
        places = places_search(q)
        new = 0
        for p in places:
            pid = p.get("id","")
            if pid and pid not in all_places:
                all_places[pid] = p; new += 1
        print(f" {len(places)} Treffer ({new} neu)")
        time.sleep(1.5)

    print(f"\n→ {len(all_places)} einzigartige Betriebe gefunden")

    # Phase 2: Zu Leads umwandeln + vorfiltern
    print("\nPHASE 2: Klassifizieren und Scoring …")
    leads = []
    for p in all_places.values():
        name    = p.get("displayName",{}).get("text","").strip()
        phone   = p.get("internationalPhoneNumber","") or ""
        website = p.get("websiteUri","") or ""
        rating  = p.get("rating",0) or 0
        reviews = p.get("userRatingCount",0) or 0
        address = p.get("formattedAddress","") or ""

        ws_class = classify_website(website)
        score    = opportunity_score(ws_class, phone, reviews)

        leads.append({
            "name": name, "phone": phone, "website": website,
            "ws_class": ws_class, "score": score,
            "address": address, "rating": f"{rating:.1f} ({reviews} Bew.)" if rating else "–",
            "email": "", "vorname": "", "nachname": "",
        })

    # Alle behalten (auch mit Website — Innendekorateure sind spezifisch genug)
    leads.sort(key=lambda x: -x["score"])
    print(f"→ {len(leads)} Leads nach Score sortiert")

    # Phase 3: Kontaktdaten crawlen
    print(f"\nPHASE 3: Websites crawlen für E-Mail + Inhaber …")
    for i, lead in enumerate(leads, 1):
        ws = lead.get("website","")
        print(f"  [{i:>2}/{len(leads)}] {lead['name'][:40]:<40}", end="", flush=True)
        if ws:
            em, vor, nach, rolle = await extract_contact_claude(ws, lead["name"])
            lead["email"]   = em
            lead["vorname"] = vor
            lead["nachname"]= nach
            found = [x for x in ["📧" if em else "", "👤" if vor else ""] if x]
            print(f" {' '.join(found) if found else '–'}")
        else:
            print(" kein Website")
        await asyncio.sleep(0.5)

    # Phase 4: Export
    print(f"\nPHASE 4: Exportieren …")
    build_excel(leads, OUT_XLSX)
    build_csv(leads, OUT_CSV)

    # Statistik
    with_phone  = sum(1 for l in leads if l["phone"])
    with_email  = sum(1 for l in leads if l["email"])
    with_name   = sum(1 for l in leads if l["vorname"])
    high_score  = sum(1 for l in leads if l["score"] >= 75)

    print(f"""
{"="*65}
ERGEBNIS — Bern Innendekorateure
{"="*65}
  Gesamt Betriebe:      {len(leads)}
  Mit Telefon:          {with_phone} ({with_phone*100//max(1,len(leads))} %)
  Mit E-Mail:           {with_email} ({with_email*100//max(1,len(leads))} %)
  Mit Inhabername:      {with_name} ({with_name*100//max(1,len(leads))} %)
  Score ≥ 75 (sehr hoch): {high_score}

Top 5:""")
    for l in leads[:5]:
        name_str = f"{l['vorname']} {l['nachname']}".strip() or "–"
        print(f"  [{l['score']:>3}] {l['name'][:35]:<35} {name_str}")

    print(f"\n→ Excel: {OUT_XLSX}")
    print(f"→ CSV:   {OUT_CSV}")

if __name__ == "__main__":
    asyncio.run(main())
