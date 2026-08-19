# -*- coding: utf-8 -*-
"""Erzeugt Proton-Sheets-kompatible Exporte aus der Lead-Datei.

Hintergrund: openpyxl speichert Texte als <is><t> (inlineStr) ohne
xl/sharedStrings.xml. Das ist gültiges OOXML, wird aber von schlanken
Web-Importern (u. a. Proton Sheets) oft nicht gelesen -> leere/fehlgeschlagene
Importe. xlsxwriter schreibt stattdessen eine sharedStrings-Tabelle.
"""
import csv, os, sys
from openpyxl import load_workbook
import xlsxwriter

SRC = sys.argv[1] if len(sys.argv) > 1 else "leads/ZERO_Umzugsfirmen_Leads_Bern.xlsx"
OUTDIR = "leads/proton"
os.makedirs(OUTDIR, exist_ok=True)

wb = load_workbook(SRC, data_only=True)
ws = wb[wb.sheetnames[0]]
rows = [[("" if c.value is None else c.value) for c in r] for r in ws.iter_rows()]
header, body = rows[0], rows[1:]
ncols = len(header)

# ---------- 1) CSV (UTF-8 mit BOM, RFC4180) ----------
csv_path = os.path.join(OUTDIR, "ZERO_Umzugsfirmen_Leads_Bern.csv")
with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f, delimiter=",", quotechar='"', quoting=csv.QUOTE_MINIMAL, lineterminator="\r\n")
    w.writerow(header)
    for r in body:
        w.writerow(["" if v is None else v for v in r])

# ---------- 2) Kompatibles XLSX (sharedStrings, ohne Table-Objekt) ----------
xlsx_path = os.path.join(OUTDIR, "ZERO_Umzugsfirmen_Leads_Bern_Proton.xlsx")
book = xlsxwriter.Workbook(xlsx_path, {"constant_memory": False, "strings_to_urls": False})
sh = book.add_worksheet("Leads Bern")

f_hdr = book.add_format({"bold": True, "font_color": "#FFFFFF", "bg_color": "#1F3864",
                         "align": "center", "valign": "vcenter", "text_wrap": True, "border": 1})
f_txt = book.add_format({"valign": "top", "text_wrap": True, "border": 1})
f_num = book.add_format({"valign": "top", "align": "center", "border": 1})
f_sales = book.add_format({"valign": "top", "text_wrap": True, "border": 1, "bg_color": "#F2F2F2"})
PRIO = {p: book.add_format({"bold": True, "align": "center", "valign": "top", "border": 1, "bg_color": bg})
        for p, bg in (("A", "#C6EFCE"), ("B", "#FFEB9C"), ("C", "#FFC7CE"))}

sh.write_row(0, 0, header, f_hdr)
SALES = set(range(26, 42))          # 0-basiert: "Call-Status" .. "Notizen"
NUMS  = {0: None, 2: f_num, 16: f_num, 20: f_num, 39: f_num}

for i, r in enumerate(body, start=1):
    for c in range(ncols):
        v = r[c] if c < len(r) else ""
        if c == 1:
            sh.write_string(i, c, str(v), PRIO.get(str(v), f_txt)); continue
        fmt = NUMS.get(c) or (f_sales if c in SALES else f_txt)
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            sh.write_number(i, c, v, fmt)
        else:
            sh.write_string(i, c, "" if v is None else str(v), fmt)

WIDTHS = [10,9,11,38,18,18,30,22,44,16,34,30,40,46,34,52,13,78,56,22,15,34,78,12,52,60,
          20,18,18,16,26,22,20,18,20,20,20,26,16,12,18,34]
for c, w in enumerate(WIDTHS[:ncols]):
    sh.set_column(c, c, w)
sh.set_row(0, 42)
sh.freeze_panes(1, 3)
sh.autofilter(0, 0, len(body), ncols - 1)
book.close()

# ---------- Kontrolle ----------
import zipfile
z = zipfile.ZipFile(xlsx_path)
has_ss = "xl/sharedStrings.xml" in z.namelist()
has_tbl = any(n.startswith("xl/tables/") for n in z.namelist())
with open(csv_path, encoding="utf-8-sig") as f:
    n_csv = sum(1 for _ in csv.reader(f))
print(f"CSV   : {csv_path}  ({n_csv} Zeilen inkl. Kopfzeile, {os.path.getsize(csv_path)/1024:.0f} KB)")
print(f"XLSX  : {xlsx_path}  ({len(body)+1} Zeilen x {ncols} Spalten, {os.path.getsize(xlsx_path)/1024:.0f} KB)")
print(f"        sharedStrings.xml vorhanden: {has_ss} | Table-Objekt entfernt: {not has_tbl}")
