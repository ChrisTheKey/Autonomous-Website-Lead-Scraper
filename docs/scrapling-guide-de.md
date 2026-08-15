# Scrapling — Dein kostenloser Lead-Roboter

> Übernommen aus dem veröffentlichten Google-Doc `scrapling-guide-de`
> ([Quelle](https://docs.google.com/document/d/e/2PACX-1vTdKwfTr2XbE2SI7nlRexsoIj1VcRstP8IyQFYn93IUPPqsFWa0gveLD3jpXbzQZRwdZmIfx7FTqbAX/pub)),
> von `@alan.buildz`, Stand Juni 2026.
>
> **Hinweis:** Der Guide beschreibt `stealthy_fetch` (Cloudflare-Bypass) sowie das Scrapen von
> LinkedIn und Indeed. Beides steht im Widerspruch zum Abschnitt
> [„What Is Deliberately NOT Implemented"](../README.md#what-is-deliberately-not-implemented)
> im README dieses Repos. Das Dokument liegt hier als Referenz — es ist nicht Teil der Pipeline,
> nichts davon ist installiert oder verdrahtet.

Das Tool aus dem Video: verwandelt Claude in einen Lead-Experten, der jede Website scrapt und dir
komplette Kontaktlisten baut — kostenlos.

## So nutzt du diesen Guide

1. Wähl deinen Weg: den Link manuell installieren (Weg 1) oder Claude per Prompt alles selbst
   einrichten lassen (Weg 2, empfohlen).
2. Installier Scrapling einmal — danach ist es dauerhaft in Claude verfügbar.
3. Schnapp dir einen der 3 Prompts, setz deine Quell-URL ein und schick ihn an Claude.

---

## Das Problem — Kunden zu finden kostet dich Stunden oder teure Tools

Leads sammelst du normalerweise von Hand: Seite für Seite durchklicken, Namen und Nummern
rauskopieren, in eine Tabelle tippen. Stunden Arbeit für eine einzige Liste — und am nächsten Tag
ist sie schon wieder veraltet.

Die Alternative sind teure Scraping-Tools wie Apify & Co., die schnell 50–100 € im Monat kosten und
trotzdem ständig an Bot-Schutz wie Cloudflare scheitern. Du zahlst also dafür, langsamer zu sein.

**Warum dich das bremst**

| | |
|---|---|
| Was passiert | Du recherchierst manuell oder mietest ein Tool für 50–100 €/Monat. |
| Die Folge | Stunden verschwendet, laufende Kosten, blockierte Seiten, veraltete Listen. |
| Das Ziel | Claude zieht dir die Daten selbst — kostenlos, in Minuten, von fast jeder Seite. |

---

## Die Lösung — Scrapling macht Claude zu deinem Lead-Experten

Sobald Scrapling einmal installiert ist, sitzt es direkt in Claude. Du sagst z. B. „scrape mir diese
Trefferliste und zieh alle Telefonnummern raus" — und Claude liefert dir eine saubere Liste zurück.
Es ersetzt teure Tools wie Apify komplett für 0 €.

Der Scraper läuft auf praktisch jeder Seite — LinkedIn, Indeed, Reddit, Verzeichnisse — und umgeht
dank Stealth-Modus auch Cloudflare-Schutz. Nutzbar für Leads, Konkurrenz-Analyse, Immobilien oder
Job-Suche.

**Auf einen Blick**

| | |
|---|---|
| Entwickler | D4Vinci (Open Source) |
| Preis | komplett kostenlos (BSD-3-Lizenz) |
| Umfang | 67.400+ Stars · v0.4.9 · Python 3.10+ |
| Verbreitung | über 65.000 Nutzer |
| Modi | `get` / `fetch` / `stealthy_fetch` (Bot-Bypass) + Sessions — alles direkt aus Claude steuerbar |

---

## Installation — 2 Wege

Du hast zwei Wege. Weg 1: die Befehle selbst im Terminal ausführen. Weg 2 (empfohlen): den Prompt
kopieren und Claude alles selbst installieren lassen.

### Weg 1 · Die Befehle (manuell)

Das Repo: [github.com/D4Vinci/Scrapling](https://github.com/D4Vinci/Scrapling)

Installier Scrapling samt MCP-Server und häng ihn an Claude:

```bash
pip install "scrapling[ai]"
scrapling install

# Pfad finden (Mac: which / Windows: where):
which scrapling

# In Claude Code registrieren (Pfad oben einsetzen):
claude mcp add ScraplingServer "/Users/DU/.venv/bin/scrapling" mcp
```

Danach Claude Code komplett neu starten. (Claude Desktop: ☰ → Settings → Developer → Edit Config
und folgenden Block einfügen, Pfad ersetzen.)

```json
{
  "mcpServers": {
    "ScraplingServer": {
      "command": "/Users/DU/.venv/bin/scrapling",
      "args": ["mcp"]
    }
  }
}
```

### Weg 2 · Der Prompt (automatisch, empfohlen)

Kopier alles zwischen den Scheren und schick es Claude Code — es installiert und verbindet
Scrapling selbst:

```text
✂ AB HIER KOPIEREN ──────────────────────────────

Installiere und konfiguriere das Web-Scraping-Tool
"Scrapling" als MCP-Server fuer dich selbst.
Mach es Schritt fuer Schritt:

1. Fuehre im Terminal aus:
   pip install "scrapling[ai]"
   scrapling install

2. Finde den Pfad zur Executable:
   which scrapling   (Windows: where scrapling)

3. Registriere den MCP-Server (Pfad aus Schritt 2):
   claude mcp add ScraplingServer "<PFAD>" mcp

4. Sag mir, wann ich Claude Code neu starten soll.
   Bestaetige danach, dass der ScraplingServer
   verbunden ist, und liste seine Tools auf.

✂ BIS HIER KOPIEREN ─────────────────────────────
```

---

## Die Top 3 Prompts — Leads, Konkurrenz & Jobs

Jeder Prompt ist fertig formuliert — ersetz nur den `<Platzhalter>` mit deiner Quell-URL und schick
ihn an Claude. Wichtig: Scrapling scrapt die Seite, die du ihm gibst (Google-Maps-Suche,
Verzeichnis, Indeed), keine eigene Suchmaschine.

### Prompt 1 · Lead-Listen bauen (Kaltakquise)

```text
Du bist mein Recherche-Assistent fuer Kaltakquise.
Nutze das Tool ScraplingServer und scrape diese Seite:
<SUCH-URL  z.B. Google-Maps "Zahnaerzte Berlin Mitte"
oder eine Gelbe-Seiten-Trefferliste>.
Blockiert/dynamisch? Nutze stealthy_fetch.

Zieh von JEDEM Treffer: Name, Ansprechpartner, Telefon,
E-Mail, Adresse, Website-URL, Bewertung.
Regeln: fehlendes Feld -> "-"; jede Zeile OHNE Website
mit "HEISSER LEAD" taggen; Dubletten per Telefon raus.
Ausgabe als CSV (Spalten in dieser Reihenfolge),
"HEISSER LEAD" zuerst. Am Ende: Anzahl Leads gesamt
und davon ohne Website.
```

### Prompt 2 · Konkurrenz-Analyse (Battlecard)

```text
Du bist mein Wettbewerbs-Analyst. Nutze ScraplingServer
und scrape die Website meines Konkurrenten: <URL>
(inkl. Unterseiten Leistungen/Preise/Ueber-uns via
bulk_get). Bei Bot-Schutz: stealthy_fetch.

Erstell eine Battlecard mit:
1) Angebot  2) Preise  3) Zielgruppe & Positionierung
4) Top-5 Verkaufsargumente + Keywords
5) Call-to-Actions  6) Schwachstellen.

Vergleich dann mit meinem Angebot: <2-3 Saetze> und gib
mir 3 konkrete Hebel, um sie zu schlagen (je 1 Satz).
```

### Prompt 3 · Jobs & Aufträge aufspüren

```text
Du bist mein Job-/Auftrags-Scout. Nutze ScraplingServer
und scrape diese Suchergebnis-Seite:
<JOBS-URL  Indeed/LinkedIn-Suche mit deinen Filtern>.
LinkedIn/Indeed blocken -> stealthy_fetch.

Zieh je Anzeige: Jobtitel, Firma, Ort (+Remote), Datum,
Gehalt, direkter Link.
Filter auf alles mit "<dein Keyword>" in Titel/Text,
sortier nach Datum (neueste zuerst).
Gib die Top 10 als nummerierte Liste, je 1 Zeile warum
es passt + Link. Weniger als 10? Sag es ehrlich, statt
die Liste aufzufuellen.
```

---

## Fertig — ab jetzt besorgt Claude dir die Kunden

Egal welchen Weg du genommen hast — Scrapling steckt jetzt in Claude. Eine URL, ein Prompt, und du
hast eine fertige Lead-, Konkurrenz- oder Job-Liste, für die andere stundenlang klicken oder 100 €
im Monat zahlen. Genau deshalb nutzen schon über 65.000 Leute diesen Cheat-Code.

**Quellen:** [github.com/D4Vinci/Scrapling](https://github.com/D4Vinci/Scrapling) ·
[scrapling.readthedocs.io](https://scrapling.readthedocs.io) · Stand Juni 2026, Zahlen können sich
ändern.
