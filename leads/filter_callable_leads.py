# -*- coding: utf-8 -*-
"""Filtert die Lead-Liste auf anrufbare Leads (Entscheidername + Telefonnummer
vorhanden) und schreibt Proton-Sheets-kompatible Exporte.

  --strict  verlangt Vor- UND Nachname (statt mindestens einem von beiden)
"""
import csv, os, sys
from openpyxl import load_workbook
import xlsxwriter

args = [a for a in sys.argv[1:] if not a.startswith("--")]
STRICT = "--strict" in sys.argv
SRC = args[0] if args else "leads/ZERO_Umzugsfirmen_Leads_Bern.xlsx"
OUTDIR = "leads/proton"
os.makedirs(OUTDIR, exist_ok=True)
suffix = "_Anrufliste_strikt" if STRICT else "_Anrufliste"

wb = load_workbook(SRC, data_only=True)
ws = wb[wb.sheetnames[0]]
rows = [[("" if c.value is None else c.value) for c in r] for r in ws.iter_rows()]
H, body = rows[0], rows[1:]
iVN, iNN, iTEL = H.index("Vorname Entscheider"), H.index("Nachname Entscheider"), H.index("Telefonnummer")

def missing(v):
    s = str(v).strip()
    return s == "" or s.lower().startswith("nicht gefunden")

def has_name(r):
    return (not missing(r[iVN]) and not missing(r[iNN])) if STRICT \
        else (not missing(r[iVN]) or not missing(r[iNN]))

keep = [r for r in body if has_name(r) and not missing(r[iTEL])]
drop = [r for r in body if r not in keep]
ncols = len(H)

# ---------- CSV (UTF-8 mit BOM, RFC4180) ----------
csv_path = os.path.join(OUTDIR, f"ZERO_Umzugsfirmen_Leads_Bern{suffix}.csv")
with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f, quoting=csv.QUOTE_MINIMAL, lineterminator="\r\n")
    w.writerow(H)
    for r in keep:
        w.writerow(r)

# ---------- XLSX (sharedStrings, ohne Table-Objekt) ----------
xlsx_path = os.path.join(OUTDIR, f"ZERO_Umzugsfirmen_Leads_Bern{suffix}.xlsx")
book = xlsxwriter.Workbook(xlsx_path, {"strings_to_urls": False})
sh = book.add_worksheet("Leads Bern")
f_hdr = book.add_format({"bold": True, "font_color": "#FFFFFF", "bg_color": "#1F3864",
                         "align": "center", "valign": "vcenter", "text_wrap": True, "border": 1})
f_txt = book.add_format({"valign": "top", "text_wrap": True, "border": 1})
f_num = book.add_format({"valign": "top", "align": "center", "border": 1})
f_sales = book.add_format({"valign": "top", "text_wrap": True, "border": 1, "bg_color": "#F2F2F2"})
PRIO = {p: book.add_format({"bold": True, "align": "center", "valign": "top", "border": 1, "bg_color": bg})
        for p, bg in (("A", "#C6EFCE"), ("B", "#FFEB9C"), ("C", "#FFC7CE"))}
SALES = set(range(26, 42))
NUMS = {2: f_num, 16: f_num, 20: f_num, 39: f_num}

sh.write_row(0, 0, H, f_hdr)
for i, r in enumerate(keep, start=1):
    for c in range(ncols):
        v = r[c]
        if c == 1:
            sh.write_string(i, c, str(v), PRIO.get(str(v), f_txt)); continue
        fmt = NUMS.get(c) or (f_sales if c in SALES else f_txt)
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            sh.write_number(i, c, v, fmt)
        else:
            sh.write_string(i, c, str(v), fmt)

WIDTHS = [10,9,11,38,18,18,30,22,44,16,34,30,40,46,34,52,13,78,56,22,15,34,78,12,52,60,
          20,18,18,16,26,22,20,18,20,20,20,26,16,12,18,34]
for c, w in enumerate(WIDTHS[:ncols]):
    sh.set_column(c, c, w)
sh.set_row(0, 42)
sh.freeze_panes(1, 3)
sh.autofilter(0, 0, len(keep), ncols - 1)
book.close()

print(f"Modus: {'strikt (Vor- UND Nachname)' if STRICT else 'normal (Vor- ODER Nachname)'}")
print(f"Behalten: {len(keep)} | Entfernt: {len(drop)}")
print(f"CSV : {csv_path} ({os.path.getsize(csv_path)/1024:.0f} KB)")
print(f"XLSX: {xlsx_path} ({os.path.getsize(xlsx_path)/1024:.0f} KB)")
print("\nEntfernte Leads (kein Entscheidername):")
for r in drop:
    print(f"  {r[0]}  {r[1]}  LS{r[2]}  {str(r[3])[:56]}")
