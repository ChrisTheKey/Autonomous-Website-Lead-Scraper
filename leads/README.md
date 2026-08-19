# ZERO – Umzugsfirmen-Leads Kanton Bern

`ZERO_Umzugsfirmen_Leads_Bern.xlsx` – Sheet **Leads Bern**, 50 recherchierte und
qualifizierte Umzugs-/Zügelfirmen aus dem Kanton Bern, sortiert nach
Priorität → Lead Score (absteigend) → Website Score (aufsteigend).

## Methodik
1. Kandidatenpool (>90 Firmen) über search.ch- und local.ch-Branchenverzeichnisse
   für Bern, Biel/Bienne, Thun, Köniz, Burgdorf, Langenthal, Steffisburg,
   Ostermundigen, Gümligen, Spiez, Interlaken, Lyss, Worb, Belp, Zollikofen,
   Konolfingen, Uetendorf, Frutigen, Zweisimmen, Huttwil, Aarwangen, Niederbipp,
   Oberburg, Thörishaus, St-Imier u. a.
2. Jede Website einzeln aufgerufen und auf Design, mobile Darstellung, Conversion-
   Strecke, Vertrauenselemente, Impressum, HTTPS/Serverstatus und SEO-Grundstruktur
   geprüft. Nur tatsächlich beobachtete Schwächen sind dokumentiert.
3. Entscheider über Impressum bzw. öffentliche Handelsregisterinformationen
   (Moneyhouse, business-monitor.ch, Northdata, handelsregister.help.ch) recherchiert.
   Nicht belegbare Angaben stehen als „Nicht gefunden“.
4. Ausgeschlossen: Vermittlungsplattformen, Branchenverzeichnisse, Firmen mit
   Handelsregistersitz ausserhalb des Kantons Bern (u. a. Welti-Furrer, Helvetia
   Transporte, National Umzüge, Zügelzentrum, Brägger & Thomann, Mammut Umzüge,
   Umzugscenter Haefeli, Express Umzug), Mehrfachstandorte derselben Firma sowie
   Betriebe ohne eigene Website oder ohne Umzugsleistung im Angebot.

## Scoring
- **Website Score 1–10** – 1 = extrem schwach, 10 = kein Neubaubedarf.
- **Lead Score 1–10** = Website-Bedarf (0–4) + Geschäftliches Potenzial (0–3)
  + Erreichbarkeit Entscheider (0–2) + Agent-Upsell-Potenzial (0–1).
- **Priorität**: A = 8–10, B = 6–7, C = 1–5.

## Sales-Felder
Spalten 27–42 sind bewusst leer bzw. neutral vorbelegt
(Call-Status = „Noch nicht angerufen“, Entscheider erreicht? = „Offen“,
Hat abgenommen? = „Offen“, Closer-Call vereinbart? = „Nein“,
Closing Probability % = leer, Anzahl Kontaktversuche = 0,
Verkaufsstatus = „Neuer Lead“). Es wurden keine Gesprächsergebnisse erfunden.

## Datei neu erzeugen
```bash
pip install openpyxl
python leads/build_leads_xlsx.py
```
