"""
Bern 100 Leads — 10 Branchen × 10 Kontakte
============================================
- Google Places API (New)  → Basisdaten + Telefon + Website
- ScrapeGraphAI + Claude   → E-Mail + Ansprechperson (Vorname/Name)
- Opportunity-Scoring      → kein/schwaches Website → hoher Score
- Export                   → Excel mit allen Kontaktfeldern

Ausführen:
    cd ~/Autonomous-Website-Lead-Scraper
    source venv/bin/activate
    python scripts/bern_100_leads_kontakte.py
"""

import re
import ssl
import time
import json
import urllib.request
import urllib.parse
import urllib.error
from pathlib import Path
from datetime import datetime

# ── openpyxl (in venv vorhanden) ────────────────────────────────────────────
try:
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
except ImportError:
    import subprocess, sys
    subprocess.check_call([sys.executable, "-m", "pip", "install", "openpyxl", "-q"])
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter

# ── Konfiguration ────────────────────────────────────────────────────────────
import os, sys
sys.path.insert(0, str(Path(__file__).parent.parent))
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
except ImportError:
    pass

GOOGLE_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "")
if not GOOGLE_KEY:
    print("FEHLER: GOOGLE_MAPS_API_KEY nicht gesetzt.")
    print("  export GOOGLE_MAPS_API_KEY=AIza...  oder in .env eintragen")
    sys.exit(1)

OUT = Path(__file__).parent.parent / "exports" / "bern_100_leads_kontakte.xlsx"

# Bern-Koordinaten
BERN_LAT, BERN_LNG = 46.9480, 7.4474
RADIUS_M = 12000   # 12 km Radius für mehr Treffer

# 10 Branchen
INDUSTRIES = [
    ("Coiffeur",             "Coiffeur Friseur Hairstudio"),
    ("Gastronomie",          "Restaurant Bistro Cafe Beiz"),
    ("Physiotherapie",       "Physiotherapie Physio Praxis"),
    ("Zahnarzt",             "Zahnarzt Zahnarztpraxis Dentist"),
    ("Autowerkstatt",        "Autowerkstatt Garage Autoservice"),
    ("Kosmetik Beauty",      "Kosmetikstudio Beauty Nail Nagel"),
    ("Reinigung",            "Reinigungsfirma Hauswartung Reinigung"),
    ("Malerbetrieb",         "Maler Gipser Malergeschäft"),
    ("Elektro",              "Elektriker Elektroinstallation Elektro"),
    ("Fotograf",             "Fotograf Fotostudio Photographer"),
]

# Domains ohne echten Webauftritt
SOCIAL_DOMAINS = {
    "facebook.com", "fb.com", "instagram.com", "twitter.com", "x.com",
    "linkedin.com", "xing.com", "youtube.com", "tiktok.com",
    "google.com", "maps.google.com", "yelp.com", "tripadvisor.com",
    "local.ch", "search.ch", "tellows.ch", "gelbeseiten.ch",
}

# Page-Builder / schwache Plattformen
WEAK_BUILDERS = {
    "wix.com", "wixsite.com", "jimdo.com", "jimdofree.com",
    "weebly.com", "squarespace.com", "wordpress.com", "blogspot.com",
    "webnode.com", "strikingly.com", "yolasite.com", "site123.com",
    "simplesite.com", "mywebsitebuilder.com", "godaddy.com",
    "one.com", "hostpoint.ch",
}

# ── Hilfsfunktionen ──────────────────────────────────────────────────────────
def classify_website(url: str) -> str:
    """Gibt zurück: 'none' | 'social' | 'weak' | 'ok'"""
    if not url:
        return "none"
    try:
        domain = urllib.parse.urlparse(url.lower()).netloc.lstrip("www.")
    except Exception:
        return "ok"
    for s in SOCIAL_DOMAINS:
        if domain == s or domain.endswith("." + s):
            return "social"
    for w in WEAK_BUILDERS:
        if domain == w or domain.endswith("." + w):
            return "weak"
    return "ok"


def head_reachable(url: str, timeout: int = 7) -> bool:
    if not url:
        return False
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        req = urllib.request.Request(url, method="HEAD",
                                     headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
            return r.status < 500
    except Exception:
        return False


def opportunity_score(ws_class: str, phone: str, reachable: bool, reviews: int) -> int:
    base = {"none": 60, "social": 55, "weak": 50, "ok": 10}.get(ws_class, 10)
    if ws_class == "ok":
        return base  # Mit funktionierender Website kein Bedarf
    score = base
    if phone:
        score += 10
    if reachable:
        score += 5
    if reviews >= 20:
        score += 8
    elif reviews >= 5:
        score += 4
    return min(100, score)


def places_search(query: str, page_token: str = None) -> dict:
    """Google Places API (New) — searchText"""
    url = "https://places.googleapis.com/v1/places:searchText"
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

    fields = (
        "places.id,places.displayName,places.formattedAddress,"
        "places.internationalPhoneNumber,places.websiteUri,"
        "places.rating,places.userRatingCount,"
        "places.primaryTypeDisplayName"
    )
    data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers={
        "Content-Type": "application/json",
        "X-Goog-Api-Key": GOOGLE_KEY,
        "X-Goog-FieldMask": fields,
    })
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())


# ── Website-Crawling für Kontaktdaten ───────────────────────────────────────
EMAIL_RE = re.compile(
    r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", re.IGNORECASE
)
# Typische Muster für Personennamen auf Kontaktseiten (DE/CH)
NAME_PATTERNS = [
    # "Ansprechpartner: Max Mustermann"
    re.compile(r"(?:Inhaber|Inhaberin|Geschäftsführer(?:in)?|Kontakt|Ansprechpartner(?:in)?|Leiter(?:in)?|Chef(?:in)?)\s*[:\-]?\s*([A-ZÄÖÜ][a-zäöü]+\s+[A-ZÄÖÜ][a-zäöüß\-]+)", re.MULTILINE),
    # "Max Mustermann" direkt nach <h3>/<strong>
    re.compile(r"<(?:h[1-4]|strong|b)[^>]*>\s*([A-ZÄÖÜ][a-zäöü]+\s+[A-ZÄÖÜ][a-zäöüß\-]+)\s*<", re.MULTILINE),
    # "Vorname Nachname" in Kontakt-Kontext
    re.compile(r"(?:Ihr\s+Ansprechpartner|Wir\s+sind|Mein\s+Name\s+ist)[^A-Z]*([A-ZÄÖÜ][a-zäöü]+\s+[A-ZÄÖÜ][a-zäöüß\-]+)", re.MULTILINE),
]

JUNK_NAMES = {
    "Öffnungszeiten", "Montag Freitag", "Cookie Policy", "Datenschutz",
    "Impressum Kontakt", "Allgemeine Geschäftsbedingungen",
}


def crawl_contact(url: str, timeout: int = 10) -> tuple[str, str, str]:
    """
    Extrahiert Kontaktdaten von einer Website.
    Versucht zuerst ScrapeGraphAI (Claude-powered), fällt auf HTML-Parsing zurück.
    Gibt (email, vorname, nachname) zurück.
    """
    if not url:
        return "", "", ""

    # ScrapeGraphAI versuchen (braucht ANTHROPIC_API_KEY)
    try:
        import asyncio
        from app.services.scrapegraph_service import extract_contact
        result = asyncio.run(extract_contact(url, timeout=timeout))
        if result.email or result.vorname:
            return result.email, result.vorname, result.nachname
    except Exception:
        pass

    # Fallback: direktes HTML-Parsing
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    base = url.rstrip("/")
    pages_to_try = [base, base + "/kontakt", base + "/contact",
                    base + "/ueber-uns", base + "/about", base + "/team"]

    found_email = found_vorname = found_nachname = ""
    headers = {"User-Agent": "Mozilla/5.0 (compatible; LeadBot/1.0)",
               "Accept": "text/html", "Accept-Language": "de-CH,de;q=0.9"}

    for page_url in pages_to_try:
        try:
            req = urllib.request.Request(page_url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
                raw = r.read(80_000)
                html = raw.decode("utf-8", errors="replace")
        except Exception:
            continue

        if not found_email:
            for em in EMAIL_RE.findall(html):
                if not any(s in em.lower() for s in ("example","noreply","no-reply","test@","@sentry")):
                    found_email = em; break

        if not found_vorname:
            plain = re.sub(r"<[^>]+>", " ", html)
            plain = re.sub(r"&[a-z]+;", " ", plain)
            plain = re.sub(r"\s+", " ", plain)
            for pat in NAME_PATTERNS:
                m = pat.search(plain)
                if m:
                    full = m.group(1).strip()
                    if full in JUNK_NAMES or len(full) > 50:
                        continue
                    parts = full.split()
                    if len(parts) >= 2:
                        found_vorname = parts[0]
                        found_nachname = " ".join(parts[1:])
                        break

        if found_email and found_vorname:
            break
        time.sleep(0.4)

    return found_email, found_vorname, found_nachname


# ── Hauptlogik ───────────────────────────────────────────────────────────────
def scrape_industry(industry_label: str, query: str, target: int = 15) -> list[dict]:
    """Scraped eine Branche und gibt rohe Treffer zurück."""
    results = []
    seen_ids = set()

    print(f"  [{industry_label}] Suche: {query}")
    try:
        resp = places_search(f"{query} Bern Schweiz")
    except Exception as e:
        print(f"    FEHLER: {e}")
        return []

    for place in resp.get("places", []):
        pid = place.get("id", "")
        if pid in seen_ids:
            continue
        seen_ids.add(pid)

        name      = place.get("displayName", {}).get("text", "")
        phone     = place.get("internationalPhoneNumber", "")
        website   = place.get("websiteUri", "")
        rating    = place.get("rating", 0) or 0
        reviews   = place.get("userRatingCount", 0) or 0
        address   = place.get("formattedAddress", "")

        ws_class  = classify_website(website)
        if ws_class == "ok":
            continue  # Nur schwache/keine Websites

        reachable = head_reachable(website) if website else False
        score     = opportunity_score(ws_class, phone, reachable, reviews)

        if score < 50:
            continue

        results.append({
            "industry":   industry_label,
            "name":       name,
            "phone":      phone,
            "website":    website or "",
            "ws_class":   ws_class,
            "reachable":  reachable,
            "reviews":    reviews,
            "rating":     rating,
            "address":    address,
            "score":      score,
            "email":      "",
            "vorname":    "",
            "nachname":   "",
        })

    print(f"    → {len(results)} qualifizierende Leads gefunden")
    return results


def enrich_with_contacts(leads: list[dict]) -> None:
    """Crawlt Websites für Email + Kontaktperson (in-place)."""
    total = len(leads)
    for i, lead in enumerate(leads, 1):
        ws = lead.get("website", "")
        if not ws:
            print(f"    [{i}/{total}] {lead['name'][:40]} — kein Website, skip crawl")
            continue
        print(f"    [{i}/{total}] crawle {ws[:60]} …", end="", flush=True)
        email, vor, nach = crawl_contact(ws)
        lead["email"]    = email
        lead["vorname"]  = vor
        lead["nachname"] = nach
        found = []
        if email:  found.append("E-Mail")
        if vor:    found.append("Name")
        print(f" {', '.join(found) if found else 'nichts gefunden'}")
        time.sleep(0.5)


# ── Excel-Export ─────────────────────────────────────────────────────────────
HEADER_FILL  = PatternFill("solid", fgColor="1A3C5E")
HEADER_FONT  = Font(name="Calibri", bold=True, color="FFFFFF", size=11)
ALT_FILL     = PatternFill("solid", fgColor="EBF3FB")
BORDER_SIDE  = Side(style="thin", color="BDD7EE")

def thin_border():
    s = BORDER_SIDE
    return Border(left=s, right=s, top=s, bottom=s)


def col_width(ws, col: int, width: float):
    ws.column_dimensions[get_column_letter(col)].width = width


def build_excel(all_leads: list[dict], path: Path) -> None:
    wb = openpyxl.Workbook()

    # ── Sheet 1: Leads ──────────────────────────────────────────────────────
    ws = wb.active
    ws.title = "Bern Leads – Kontakte"

    headers = [
        "Nr.", "Branche", "Firmenname", "Vorname", "Nachname",
        "Telefon", "E-Mail", "Ursprungs-Website", "Website-Status",
        "Opportunity Score", "Bern-Adresse",
    ]
    col_widths = [5, 18, 28, 14, 16, 18, 30, 32, 14, 10, 38]

    for c_i, (h, w) in enumerate(zip(headers, col_widths), 1):
        cell = ws.cell(row=1, column=c_i, value=h)
        cell.font   = HEADER_FONT
        cell.fill   = HEADER_FILL
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = thin_border()
        col_width(ws, c_i, w)
    ws.row_dimensions[1].height = 28

    ws_labels = {"none": "Kein Website", "social": "Nur Social Media",
                 "weak": "Schwache Website (Builder)", "ok": "Website vorhanden"}

    for row_i, lead in enumerate(all_leads, 2):
        fill = ALT_FILL if row_i % 2 == 0 else PatternFill()
        values = [
            row_i - 1,
            lead["industry"],
            lead["name"],
            lead["vorname"],
            lead["nachname"],
            lead["phone"],
            lead["email"],
            lead["website"],
            ws_labels.get(lead["ws_class"], lead["ws_class"]),
            lead["score"],
            lead["address"],
        ]
        for c_i, val in enumerate(values, 1):
            cell = ws.cell(row=row_i, column=c_i, value=val)
            cell.fill      = fill
            cell.border    = thin_border()
            cell.alignment = Alignment(vertical="center", wrap_text=(c_i in (3, 7, 8, 11)))
            if c_i == 10:
                cell.alignment = Alignment(horizontal="center", vertical="center")
                # Farb-Codierung Score
                score = lead["score"]
                if score >= 75:
                    cell.font = Font(bold=True, color="006400")
                elif score >= 60:
                    cell.font = Font(bold=True, color="856404")
                else:
                    cell.font = Font(color="555555")
        ws.row_dimensions[row_i].height = 20

    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions

    # Score-Legende
    row_after = len(all_leads) + 3
    ws.cell(row=row_after, column=1, value="Opportunity Score:").font = Font(bold=True)
    ws.cell(row=row_after+1, column=1, value="≥ 75 = Sehr hoch (kein/social Website, Telefon vorhanden)")
    ws.cell(row=row_after+2, column=1, value="60–74 = Hoch (schwaches Website, Redesign-Potenzial)")
    ws.cell(row=row_after+3, column=1, value="50–59 = Mittel (grundsätzlich geeignet)")

    # ── Sheet 2: Scoring-Modell ──────────────────────────────────────────────
    ws2 = wb.create_sheet("Scoring-Modell")
    scoring_rows = [
        ("Faktor", "Punkte", "Begründung"),
        ("Kein Website", "60", "Höchster Webdesign-Bedarf"),
        ("Nur Social Media", "55", "Kein eigener Auftritt, sozialer Kanal reicht nicht"),
        ("Schwache Website (Wix/Jimdo etc.)", "50", "Veralteter / einfacher Auftritt, Redesign-Potenzial"),
        ("Website vorhanden (modern)", "10", "Geringer Bedarf → wird herausgefiltert"),
        ("+ Telefonnummer vorhanden", "+10", "Direktkontakt möglich"),
        ("+ Website erreichbar (HTTP OK)", "+5", "Aktiv, aber schwach"),
        ("+ ≥ 5 Google-Bewertungen", "+4", "Etabliertes Unternehmen"),
        ("+ ≥ 20 Google-Bewertungen", "+8", "Gut etabliert, lohnt sich"),
        ("Maximum", "100", "Gedeckelt bei 100"),
    ]
    for r_i, row in enumerate(scoring_rows, 1):
        for c_i, val in enumerate(row, 1):
            cell = ws2.cell(row=r_i, column=c_i, value=val)
            if r_i == 1:
                cell.font = HEADER_FONT
                cell.fill = HEADER_FILL
                cell.alignment = Alignment(horizontal="center")
            elif r_i % 2 == 0:
                cell.fill = ALT_FILL
            cell.border = thin_border()
    for c, w in zip([1, 2, 3], [38, 10, 45]):
        ws2.column_dimensions[get_column_letter(c)].width = w

    # ── Sheet 3: Statistiken ─────────────────────────────────────────────────
    ws3 = wb.create_sheet("Statistiken")
    by_industry = {}
    by_ws = {"none": 0, "social": 0, "weak": 0}
    email_count = 0
    contact_count = 0

    for lead in all_leads:
        ind = lead["industry"]
        by_industry[ind] = by_industry.get(ind, 0) + 1
        ws_c = lead["ws_class"]
        if ws_c in by_ws:
            by_ws[ws_c] += 1
        if lead["email"]:
            email_count += 1
        if lead["vorname"]:
            contact_count += 1

    stats = [
        ("Statistiken", ""),
        ("Gesamt Leads", len(all_leads)),
        ("Mit E-Mail", email_count),
        ("Mit Ansprechperson", contact_count),
        ("", ""),
        ("Website-Status", "Anzahl"),
        ("Kein Website", by_ws["none"]),
        ("Nur Social Media", by_ws["social"]),
        ("Schwache Website", by_ws["weak"]),
        ("", ""),
        ("Branche", "Leads"),
    ] + [(k, v) for k, v in sorted(by_industry.items(), key=lambda x: -x[1])]

    for r_i, (label, value) in enumerate(stats, 1):
        c1 = ws3.cell(row=r_i, column=1, value=label)
        c2 = ws3.cell(row=r_i, column=2, value=value)
        if label in ("Statistiken", "Website-Status", "Branche"):
            c1.font = HEADER_FONT; c1.fill = HEADER_FILL
            c2.font = HEADER_FONT; c2.fill = HEADER_FILL
        c1.border = thin_border(); c2.border = thin_border()
    ws3.column_dimensions["A"].width = 30
    ws3.column_dimensions["B"].width = 12

    # ── Metadaten ────────────────────────────────────────────────────────────
    wb.properties.title   = "Bern B2B Leads – Kontaktdaten"
    wb.properties.creator = "Autonomous Lead Scraper"
    wb.properties.created = datetime.utcnow()

    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
    print(f"\n✓ Excel gespeichert: {path}")


# ── Hauptprogramm ─────────────────────────────────────────────────────────────
def main():
    print("=" * 65)
    print("Bern 100 Leads — 10 Branchen × 10 Kontakte")
    print("=" * 65)
    print(f"Radius: {RADIUS_M // 1000} km um Bern-Zentrum")
    print()

    all_leads: list[dict] = []
    per_industry: dict[str, list] = {}

    # Phase 1: Scraping
    print("PHASE 1: Google Places scrapen …")
    for industry_label, query in INDUSTRIES:
        leads = scrape_industry(industry_label, query, target=15)
        leads.sort(key=lambda x: x["score"], reverse=True)
        per_industry[industry_label] = leads[:10]  # max 10 pro Branche
        time.sleep(1.5)

    # Phase 2: Website-Crawling für Kontaktdaten
    print("\nPHASE 2: Websites crawlen (E-Mail + Ansprechperson) …")
    for industry_label, leads in per_industry.items():
        print(f"\n  [{industry_label}] — {len(leads)} Leads")
        enrich_with_contacts(leads)
        all_leads.extend(leads)

    # Nach Score sortieren (branchenübergreifend für Übersicht)
    all_leads.sort(key=lambda x: (-x["score"], x["industry"]))

    # Statistik
    print("\n" + "=" * 65)
    print(f"Gesamt: {len(all_leads)} Leads in {len(per_industry)} Branchen")
    email_n   = sum(1 for l in all_leads if l["email"])
    contact_n = sum(1 for l in all_leads if l["vorname"])
    print(f"Mit E-Mail:          {email_n} ({email_n*100//max(1,len(all_leads))} %)")
    print(f"Mit Ansprechperson:  {contact_n} ({contact_n*100//max(1,len(all_leads))} %)")

    print("\nTop-5 Leads:")
    for lead in all_leads[:5]:
        print(f"  [{lead['score']:>3}] {lead['name'][:35]:<35} {lead['industry']}")

    # Phase 3: Excel exportieren
    print("\nPHASE 3: Excel erstellen …")
    build_excel(all_leads, OUT)

    print("\n--- Rechtsgrundlage ---")
    print("  Quelle: Google Places API (öffentliche Gewerbedaten)")
    print("  Basis : Berechtigtes Interesse B2B (revDSG Art. 31)")
    print("  Nur Geschäftskontakte, keine Privatpersonen")
    print(f"\n→ Datei: {OUT}")


if __name__ == "__main__":
    main()
