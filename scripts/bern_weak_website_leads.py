"""
Scrape Bern leads with weak/no websites, verify them, export prioritised Excel.
Run: python scripts/bern_weak_website_leads.py
"""

import asyncio
import json
import os
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

API = "http://localhost:8000"
OUT = Path(__file__).parent.parent / "exports" / "bern_schwache_websites.xlsx"

BERN_INDUSTRIES = [
    "Restaurant", "Café", "Bäckerei", "Metzgerei",
    "Coiffeur", "Kosmetikstudio", "Nagelstudio",
    "Schreinerei", "Malerbetrieb", "Sanitär", "Elektriker", "Schlosserei",
    "Gartenbau", "Reinigungsfirma", "Umzugsunternehmen",
    "Zahnarzt", "Physiotherapie", "Massage", "Optiker",
    "Fotograf", "Werbeagentur", "Druckerei",
    "Fitness", "Yoga", "Pilates",
    "Immobilien", "Treuhand", "Buchhalter",
]


def post(path, body):
    data = json.dumps(body).encode()
    req = urllib.request.Request(f"{API}{path}", data=data,
                                  headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())


def get(path):
    with urllib.request.urlopen(f"{API}{path}", timeout=15) as r:
        return json.loads(r.read())


def verify_website(url: str) -> tuple[bool, str]:
    """Returns (is_reachable, note)."""
    if not url:
        return False, "Kein Website-URL"
    try:
        req = urllib.request.Request(url, method="HEAD",
                                      headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=8) as r:
            return True, f"HTTP {r.status}"
    except urllib.error.HTTPError as e:
        return e.code < 500, f"HTTP {e.code}"
    except Exception as e:
        return False, str(e)[:60]


async def get_contacts():
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from app.models.contact import Contact

    db_url = os.getenv("DATABASE_URL", "")
    engine = create_async_engine(db_url, echo=False)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as db:
        result = await db.execute(select(Contact))
        contacts = {c.company_id: c for c in result.scalars().all() if c.company_id}
    await engine.dispose()
    return contacts


def opportunity_score(company, contact) -> tuple[int, str]:
    lt = company.get("lead_type", "")
    base = {"no_website": 55, "weak_website_candidate": 60}.get(lt, 5)
    bonus = {"high_priority": 25, "medium_priority": 12}.get(company.get("lead_priority", ""), 0)
    phone_pts  = 8  if company.get("phone") else 0
    email_pts  = 12 if (contact and contact.email) else 0
    addr_pts   = 5  if company.get("address") else 0
    score = min(100, base + bonus + phone_pts + email_pts + addr_pts)

    reasons = []
    if lt == "no_website":           reasons.append("Kein Website")
    elif lt == "weak_website_candidate": reasons.append("Schwache Website")
    if bonus > 0:                    reasons.append("Hohe interne Priorität")
    if company.get("phone"):         reasons.append("Tel. vorhanden")
    if contact and contact.email:    reasons.append("E-Mail vorhanden")
    return score, "; ".join(reasons)


def main():
    print("=" * 65)
    print("Bern — Leads mit schwacher/fehlender Website scrapen & prüfen")
    print("=" * 65)

    # ── Step 1: Trigger all Bern searches ────────────────────────────────
    print(f"\n[1/5] Triggering {len(BERN_INDUSTRIES)} searches in Bern...")
    search_ids = []
    for industry in BERN_INDUSTRIES:
        try:
            result = post("/search", {
                "industry": industry,
                "location": "Bern",
                "max_results": 15,
            })
            search_ids.append(result["id"])
            print(f"  ✓ {industry} → Search-ID {result['id']}")
            time.sleep(1.5)
        except Exception as e:
            print(f"  ✗ {industry}: {e}")

    print(f"\n[2/5] Warte 5 Min auf Celery-Enrichment ({len(search_ids)} Suchen)...")
    for i in range(5):
        time.sleep(60)
        print(f"  ... {i+1}/5 Min")

    # ── Step 2: Fetch companies ───────────────────────────────────────────
    print("\n[3/5] Lade Companies aus API...")
    companies = get("/companies?limit=500")
    print(f"  → {len(companies)} Einträge total in DB")

    contacts = asyncio.run(get_contacts())

    # Filter: Bern + weak/no website
    bern_leads = [
        c for c in companies
        if (c.get("location") or "").lower() in ("bern", "berne")
        and c.get("lead_type") in ("weak_website_candidate", "no_website")
    ]
    print(f"  → {len(bern_leads)} Bern-Leads mit schwacher/fehlender Website")

    # ── Step 3: Score ─────────────────────────────────────────────────────
    print("\n[4/5] Scoring & Verifizierung...")
    rows = []
    for c in bern_leads:
        contact = contacts.get(c["id"])
        score, reason = opportunity_score(c, contact)
        if score < 55:
            continue  # only high-opportunity leads

        website = c.get("website", "")
        reachable, http_note = verify_website(website) if website else (False, "Kein Website")
        print(f"  [{score:>3}] {c.get('name','')[:35]:<35} | {http_note}")

        rows.append({
            "score":           score,
            "score_grund":     reason,
            "name":            c.get("name", ""),
            "industry":        c.get("industry", ""),
            "address":         c.get("address", ""),
            "phone":           c.get("phone", ""),
            "email":           (contact.email if contact else "") or "",
            "website":         website,
            "website_status":  "Kein Website" if c.get("lead_type") == "no_website" else "Schwache Website",
            "erreichbar":      "Ja" if reachable else ("Kein Website" if not website else "Nicht erreichbar"),
            "http_status":     http_note,
            "lead_type":       c.get("lead_type", ""),
            "quelle":          "Google Places API (öffentl. Geschäftsdaten, Bern)",
            "rechtsgrundlage": "Berechtigtes Interesse B2B (revDSG Art. 31)",
            "status":          "NEW",
        })

    rows.sort(key=lambda r: r["score"], reverse=True)
    print(f"\n  → {len(rows)} Leads nach Scoring-Filter (Score ≥ 55)")

    if not rows:
        print("\n⚠  Keine Leads gefunden — zu früh abgefragt oder Celery noch nicht fertig.")
        print("   Warte weitere 3 Min und versuche erneut...")
        time.sleep(180)
        companies = get("/companies?limit=500")
        bern_leads = [
            c for c in companies
            if (c.get("location") or "").lower() in ("bern", "berne")
            and c.get("lead_type") in ("weak_website_candidate", "no_website")
        ]
        for c in bern_leads:
            contact = contacts.get(c["id"])
            score, reason = opportunity_score(c, contact)
            website = c.get("website", "")
            reachable, http_note = verify_website(website) if website else (False, "Kein Website")
            rows.append({
                "score": score, "score_grund": reason,
                "name": c.get("name",""), "industry": c.get("industry",""),
                "address": c.get("address",""), "phone": c.get("phone",""),
                "email": (contact.email if contact else "") or "",
                "website": website,
                "website_status": "Kein Website" if c.get("lead_type")=="no_website" else "Schwache Website",
                "erreichbar": "Ja" if reachable else ("Kein Website" if not website else "Nicht erreichbar"),
                "http_status": http_note, "lead_type": c.get("lead_type",""),
                "quelle": "Google Places API", "rechtsgrundlage": "Berechtigtes Interesse B2B (revDSG Art. 31)",
                "status": "NEW",
            })
        rows.sort(key=lambda r: r["score"], reverse=True)

    # ── Step 4: Export Excel ──────────────────────────────────────────────
    print(f"\n[5/5] Exportiere {len(rows)} Leads als Excel...")
    build_excel(rows)
    print(f"\n✓ Fertig: {OUT}")
    print(f"  Top 5:")
    for r in rows[:5]:
        print(f"  [{r['score']:>3}] {r['name'][:40]:<40} | {r['website_status']}")


def build_excel(rows):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    wb.remove(wb.active)

    thin  = Side(style="thin", color="BDD7EE")
    bdr   = Border(left=thin, right=thin, top=thin, bottom=thin)
    C_HDR = "1F4E79"; C_SUB = "2E75B6"
    C_HI  = "E2EFDA"; C_MD  = "FFF2CC"; C_LO = "FCE4D6"

    def f(hex_c): return PatternFill("solid", fgColor=hex_c)
    def af(s=10, bold=False, col="000000"): return Font(name="Arial", size=s, bold=bold, color=col)
    def ac(wrap=True): return Alignment(horizontal="center", vertical="center", wrap_text=wrap)
    def al(wrap=True): return Alignment(horizontal="left", vertical="center", wrap_text=wrap)

    # ── Sheet 1: Leads ────────────────────────────────────────────────────
    ws = wb.create_sheet("Bern — Schwache Websites")

    COLS = [
        ("#",                   5),
        ("Opp.-Score",         11),
        ("Ampel",              10),
        ("Firma / Name",       28),
        ("Branche",            18),
        ("Adresse Bern",       30),
        ("Telefon",            15),
        ("E-Mail",             28),
        ("Website",            26),
        ("Website-Status",     16),
        ("Erreichbar",         12),
        ("HTTP-Status",        12),
        ("Score-Begründung",   36),
        ("Outreach-Status",    14),
        ("Quelle",             28),
        ("Rechtsgrundlage",    32),
    ]

    ws.merge_cells("A1:P1")
    ws["A1"] = "BERN — LEADS MIT SCHWACHER WEBSITE  |  Hoher Opportunity-Score  |  Helvetic Webdesign 2026"
    ws["A1"].font = Font(name="Arial", size=13, bold=True, color="FFFFFF")
    ws["A1"].fill = f(C_HDR)
    ws["A1"].alignment = ac()
    ws.row_dimensions[1].height = 28

    ws.merge_cells("A2:P2")
    ws["A2"] = (f"✓ ECHTE LEADS — Google Places API (Bern, Schweiz)  |  "
                f"Nur Leads mit schwacher/fehlender Website  |  {len(rows)} Leads  |  "
                f"Alle geprüft (HTTP-Verifizierung)")
    ws["A2"].font = Font(name="Arial", size=10, bold=True, color="1A5276")
    ws["A2"].fill = f("D6EAF8")
    ws["A2"].alignment = ac()
    ws.row_dimensions[2].height = 18

    for c_idx, (hdr, width) in enumerate(COLS, 1):
        cell = ws.cell(row=3, column=c_idx, value=hdr)
        cell.font = Font(name="Arial", size=10, bold=True, color="FFFFFF")
        cell.fill = f(C_SUB)
        cell.alignment = ac()
        cell.border = bdr
        ws.column_dimensions[get_column_letter(c_idx)].width = width
    ws.row_dimensions[3].height = 30
    ws.freeze_panes = "A4"

    for i, row in enumerate(rows, 1):
        sc = row["score"]
        bg = C_HI if sc >= 70 else (C_MD if sc >= 55 else C_LO)
        ampel = "🟢 Hoch" if sc >= 70 else ("🟡 Mittel" if sc >= 55 else "🔴 Niedrig")
        vals = [
            i, sc, ampel, row["name"], row["industry"], row["address"],
            row["phone"], row["email"], row["website"], row["website_status"],
            row["erreichbar"], row["http_status"], row["score_grund"],
            row["status"], row["quelle"], row["rechtsgrundlage"],
        ]
        for c_idx, val in enumerate(vals, 1):
            cell = ws.cell(row=i+3, column=c_idx, value=val)
            cell.font = af(bold=(c_idx <= 2))
            cell.fill = f(bg)
            cell.alignment = ac() if c_idx <= 3 else al()
            cell.border = bdr
        ws.row_dimensions[i+3].height = 16

    # ── Sheet 2: Scoring-Modell ───────────────────────────────────────────
    ws2 = wb.create_sheet("Scoring-Modell")
    ws2.column_dimensions["A"].width = 28
    ws2.column_dimensions["B"].width = 18
    ws2.column_dimensions["C"].width = 44
    ws2.column_dimensions["D"].width = 34

    scoring = [
        ("SCORING-MODELL — Opportunity-Score (0–100)", "", "", ""),
        ("", "", "", ""),
        ("KRITERIUM", "PUNKTE", "BEGRÜNDUNG", "RECHTSGRUNDLAGE"),
        ("Schwache Website", "60 (Basis)", "Website existiert, aber veraltet/lückenhaft → Redesign-Potenzial", "revDSG Art. 31 B2B"),
        ("Kein Website", "55 (Basis)", "Kein Web-Auftritt → maximaler Webdesign-Bedarf", "revDSG Art. 31 B2B"),
        ("Hohe interne Priorität", "+25", "Vom Scoring-System als top Lead eingestuft", "—"),
        ("Mittlere Priorität", "+12", "Moderates Potential", "—"),
        ("Telefon vorhanden", "+8", "Direktkontakt möglich", "—"),
        ("E-Mail vorhanden", "+12", "Primär-Kanal Outreach", "—"),
        ("Adresse vollständig", "+5", "Verifizierbar, lokaler Bezug", "—"),
        ("", "", "", ""),
        ("FILTER", "", "", ""),
        ("Score-Schwelle", "≥ 55", "Nur Leads mit hohem Opportunity-Score enthalten", ""),
        ("Geographie", "Bern (BE)", "Nur Leads aus dem Kanton/Stadt Bern", ""),
        ("Website-Typ", "Schwach / Kein Website", "Keine Leads mit professioneller Website", ""),
        ("Verifizierung", "HTTP HEAD-Request", "Jeder Website-Link geprüft (erreichbar/nicht)", ""),
        ("", "", "", ""),
        ("DATENQUELLE", "", "", ""),
        ("Google Places API", "Öffentliche Geschäftsdaten", "Nur B2B, keine Privatpersonen", "revDSG Art. 31"),
        ("Opt-Out", "Sofort supprimieren", "Aufnahme in Suppression-Liste", "revDSG Art. 30"),
        ("Aufbewahrung", "Max. 2 Jahre", "Datensparsamkeit", "revDSG Art. 6"),
    ]
    for r_i, row in enumerate(scoring, 1):
        for c_i, val in enumerate(row, 1):
            cell = ws2.cell(row=r_i, column=c_i, value=val)
            cell.alignment = al()
            cell.font = af()
            if r_i == 1:
                cell.font = Font(name="Arial", size=13, bold=True, color="FFFFFF")
                cell.fill = f(C_HDR)
            elif row[0] in ("KRITERIUM", "FILTER", "DATENQUELLE"):
                cell.font = Font(name="Arial", size=10, bold=True, color="FFFFFF")
                cell.fill = f(C_SUB)
            if val: cell.border = bdr
        ws2.row_dimensions[r_i].height = 20
    ws2.merge_cells("A1:D1")

    # ── Sheet 3: Statistik ────────────────────────────────────────────────
    ws3 = wb.create_sheet("Statistik")
    ws3.column_dimensions["A"].width = 22
    ws3.column_dimensions["B"].width = 14
    ws3.column_dimensions["C"].width = 14
    ws3.column_dimensions["D"].width = 16

    ws3.merge_cells("A1:D1")
    ws3["A1"] = f"STATISTIK — {len(rows)} Bern-Leads (Schwache Websites)"
    ws3["A1"].font = Font(name="Arial", size=12, bold=True, color="FFFFFF")
    ws3["A1"].fill = f(C_HDR)
    ws3["A1"].alignment = ac()
    ws3.row_dimensions[1].height = 26

    for c_i, h in enumerate(["Branche","Anzahl","Ø Score","Score ≥ 70"], 1):
        cell = ws3.cell(row=2, column=c_i, value=h)
        cell.font = Font(name="Arial", size=10, bold=True, color="FFFFFF")
        cell.fill = f(C_SUB); cell.alignment = ac(); cell.border = bdr

    industries = sorted(set(r["industry"] for r in rows))
    r_i = 3
    for ind in industries:
        ind_rows = [r for r in rows if r["industry"] == ind]
        avg = round(sum(r["score"] for r in ind_rows) / len(ind_rows), 1)
        hi = sum(1 for r in ind_rows if r["score"] >= 70)
        for c_i, val in enumerate([ind, len(ind_rows), avg, hi], 1):
            cell = ws3.cell(row=r_i, column=c_i, value=val)
            cell.font = af(); cell.fill = f("EBF3FB")
            cell.alignment = al() if c_i == 1 else ac(); cell.border = bdr
        r_i += 1

    for label, lo, hi_v, bg in [
        ("🟢 Score ≥ 70 (Hoch)",   70, 101, C_HI),
        ("🟡 Score 55–69 (Mittel)", 55,  70, C_MD),
    ]:
        r_i += 1
        cnt = sum(1 for r in rows if lo <= r["score"] < hi_v)
        ws3.cell(row=r_i, column=1, value=label).fill = f(bg)
        ws3.cell(row=r_i, column=1).font = af()
        ws3.cell(row=r_i, column=1).border = bdr
        ws3.cell(row=r_i, column=1).alignment = al()
        ws3.cell(row=r_i, column=2, value=cnt).fill = f(bg)
        ws3.cell(row=r_i, column=2).font = af(bold=True)
        ws3.cell(row=r_i, column=2).border = bdr
        ws3.cell(row=r_i, column=2).alignment = ac()

    for row_n in range(1, r_i+1):
        ws3.row_dimensions[row_n].height = 18

    OUT.parent.mkdir(parents=True, exist_ok=True)
    wb.save(OUT)


if __name__ == "__main__":
    main()
