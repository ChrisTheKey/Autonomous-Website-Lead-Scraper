"""
Contact extractor — liest Website-HTML und extrahiert via Claude:
  - E-Mail des Unternehmens
  - Vorname + Nachname des Inhabers / Geschäftsführers

Kein Regex-Raten. Claude liest den Text und entscheidet.
"""

from __future__ import annotations

import asyncio
import re
import ssl
from dataclasses import dataclass

import httpx
import structlog

log = structlog.get_logger()

# Seiten die bei der Suche nach Kontakten priorisiert werden
CONTACT_PATHS = [
    "/kontakt", "/contact", "/impressum", "/imprint",
    "/ueber-uns", "/ueber-mich", "/about", "/about-us",
    "/team", "/wir", "/person", "/profil",
]

# Domains die nie echte Inhabernamen enthalten
SKIP_DOMAINS = {
    "facebook.com", "instagram.com", "twitter.com", "x.com",
    "linkedin.com", "tiktok.com", "youtube.com", "google.com",
    "local.ch", "search.ch", "yellow.ch", "tripadvisor.com",
}


@dataclass
class ContactResult:
    email: str = ""
    vorname: str = ""
    nachname: str = ""
    rolle: str = ""
    source_url: str = ""


async def fetch_page(client: httpx.AsyncClient, url: str) -> str:
    """Holt HTML einer Seite, max 80 KB."""
    try:
        r = await client.get(url, timeout=10)
        return r.text[:80_000]
    except Exception:
        return ""


def html_to_text(html: str) -> str:
    """Wandelt HTML in lesbaren Plaintext um."""
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "lxml")
        # Script/Style entfernen
        for tag in soup(["script", "style", "nav", "footer", "head"]):
            tag.decompose()
        text = soup.get_text(separator="\n")
        # Leerzeilen komprimieren
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        return "\n".join(lines[:300])  # max 300 Zeilen
    except Exception:
        # Notfall: rohe Tag-Entfernung
        text = re.sub(r"<[^>]+>", " ", html)
        return re.sub(r"\s+", " ", text)[:6000]


async def extract_email_simple(text: str) -> str:
    """Einfache Regex-Extraktion für E-Mail — das funktioniert zuverlässig."""
    EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
    skip = {"noreply", "no-reply", "example", "test@", "@test", "sentry",
            "placeholder", "yourname", "name@", "@domain"}
    for m in EMAIL_RE.findall(text):
        if not any(s in m.lower() for s in skip):
            return m
    return ""


async def extract_name_with_claude(text: str, company_name: str, api_key: str) -> tuple[str, str, str]:
    """
    Schickt den Website-Text an Claude und fragt nach dem Inhabernamen.
    Gibt (vorname, nachname, rolle) zurück.
    """
    if not api_key or not text.strip():
        return "", "", ""

    try:
        import anthropic

        client = anthropic.Anthropic(api_key=api_key)

        prompt = f"""Du analysierst den Text einer Schweizer Unternehmenswebsite.
Firma: {company_name}

Website-Text (Auszug):
{text[:4000]}

Aufgabe: Finde den echten Inhaber, Geschäftsführer oder Hauptansprechpartner dieser Firma.

Regeln:
- Nur ECHTE Personennamen (Vorname + Nachname) — keine Firmennamen, keine Jobtitel allein
- Kein "Kontakt", "Impressum", "Formular", "E-Mail", "Adresse" als Name
- Falls kein Name gefunden: leere Strings zurückgeben
- Priorität: Inhaber > Geschäftsführer > Gründer > Teamleiter

Antwort NUR als JSON, kein anderer Text:
{{"vorname": "", "nachname": "", "rolle": ""}}"""

        msg = client.messages.create(
            model="claude-opus-4-8",
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}],
        )

        raw = msg.content[0].text.strip()
        # JSON extrahieren
        m = re.search(r'\{[^}]+\}', raw, re.DOTALL)
        if m:
            import json
            data = json.loads(m.group())
            vor  = (data.get("vorname") or "").strip()
            nach = (data.get("nachname") or "").strip()
            rolle = (data.get("rolle") or "").strip()

            # Validierung: muss wie ein echter Name aussehen
            if vor and nach and len(vor) > 1 and len(nach) > 1:
                # Keine Firmenwörter
                junk = {"ag", "gmbh", "bern", "schweiz", "kontakt", "impressum",
                        "adresse", "telefon", "email", "formular", "news",
                        "willkommen", "über", "home", "firma", "sie", "form"}
                if vor.lower() not in junk and nach.lower() not in junk:
                    return vor, nach, rolle

    except Exception as e:
        log.debug("claude_name_extract_failed", error=str(e))

    return "", "", ""


async def extract_contact(
    url: str,
    company_name: str = "",
    anthropic_api_key: str = "",
    timeout: int = 30,
) -> ContactResult:
    """
    Hauptfunktion: holt Website-Seiten und extrahiert Kontaktdaten.
    """
    if not url:
        return ContactResult()

    # Skip-Domains
    try:
        from urllib.parse import urlparse
        domain = urlparse(url.lower()).netloc.lstrip("www.")
        if any(domain == s or domain.endswith("." + s) for s in SKIP_DOMAINS):
            return ContactResult(source_url=url)
    except Exception:
        pass

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    base = url.rstrip("/")
    pages_to_try = [base] + [base + p for p in CONTACT_PATHS]

    email = vorname = nachname = rolle = ""
    combined_text = ""

    async with httpx.AsyncClient(
        verify=False,
        follow_redirects=True,
        timeout=10,
        headers={"User-Agent": "Mozilla/5.0 (compatible; LeadBot/1.0)"},
    ) as client:
        for page_url in pages_to_try[:5]:  # max 5 Seiten
            html = await fetch_page(client, page_url)
            if not html:
                continue

            text = html_to_text(html)
            combined_text += "\n" + text

            if not email:
                email = await extract_email_simple(text)

            await asyncio.sleep(0.3)

            if email and len(combined_text) > 2000:
                break  # Genug Material für Claude

    # Name via Claude extrahieren
    if anthropic_api_key and combined_text.strip():
        vorname, nachname, rolle = await extract_name_with_claude(
            combined_text, company_name, anthropic_api_key
        )

    return ContactResult(
        email=email,
        vorname=vorname,
        nachname=nachname,
        rolle=rolle,
        source_url=url,
    )


async def batch_extract(
    items: list[tuple[str, str]],  # [(url, company_name), ...]
    anthropic_api_key: str = "",
    concurrency: int = 4,
) -> list[ContactResult]:
    """Extrahiert Kontakte für mehrere URLs parallel."""
    sem = asyncio.Semaphore(concurrency)

    async def _one(url: str, name: str) -> ContactResult:
        async with sem:
            return await extract_contact(url, name, anthropic_api_key)

    return await asyncio.gather(*[_one(u, n) for u, n in items])
