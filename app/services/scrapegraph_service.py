"""
ScrapeGraphAI-powered contact extraction.

Uses SmartScraperGraph to extract structured contact data (email, person name)
from business websites using Claude as the LLM backend.

Usage:
    from app.services.scrapegraph_service import extract_contact
    result = await extract_contact("https://example.ch")
    # result.email, result.vorname, result.nachname
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

import structlog

from app.config import settings

log = structlog.get_logger()


@dataclass
class ContactResult:
    email: str = ""
    vorname: str = ""
    nachname: str = ""
    role: str = ""        # z.B. "Inhaber", "Geschäftsführer"
    source_url: str = ""
    method: str = ""      # "scrapegraph" | "fallback"


EXTRACT_PROMPT = """
Extrahiere die folgenden Kontaktdaten aus dieser Schweizer Unternehmenswebsite.
Nur echte, auf der Seite vorhandene Daten zurückgeben — keine Erfindungen.

Felder:
- email: E-Mail-Adresse des Unternehmens oder Ansprechpersons (kein noreply/example)
- vorname: Vorname der Hauptansprechperson (Inhaber, Geschäftsführer, etc.)
- nachname: Nachname der Hauptansprechperson
- role: Funktion der Person (z.B. "Inhaber", "Geschäftsführerin", "CEO")

Falls ein Feld nicht gefunden wird: leerer String "".
"""


def _build_graph_config() -> dict:
    """Erstellt die ScrapeGraphAI-Konfiguration mit Claude als LLM."""
    return {
        "llm": {
            "api_key":    settings.anthropic_api_key,
            "model":      "anthropic/claude-opus-4-8",
            "temperature": 0,
        },
        "verbose": False,
        "headless": True,
    }


async def extract_contact(url: str, timeout: int = 30) -> ContactResult:
    """
    Extrahiert Kontaktdaten von einer Website mit ScrapeGraphAI.
    Fällt bei Fehler auf einfaches HTML-Parsing zurück.
    """
    if not url:
        return ContactResult()

    try:
        from scrapegraphai.graphs import SmartScraperGraph

        def _run_scraper():
            graph = SmartScraperGraph(
                prompt=EXTRACT_PROMPT,
                source=url,
                config=_build_graph_config(),
            )
            return graph.run()

        # In Thread ausführen (scrapegraphai ist synchron)
        loop   = asyncio.get_event_loop()
        result = await asyncio.wait_for(
            loop.run_in_executor(None, _run_scraper),
            timeout=timeout,
        )

        if isinstance(result, dict):
            return ContactResult(
                email      = (result.get("email") or "").strip(),
                vorname    = (result.get("vorname") or "").strip(),
                nachname   = (result.get("nachname") or "").strip(),
                role       = (result.get("role") or "").strip(),
                source_url = url,
                method     = "scrapegraph",
            )

    except ImportError:
        log.warning("scrapegraphai not installed — using fallback", url=url)
    except asyncio.TimeoutError:
        log.warning("scrapegraphai timeout", url=url, timeout=timeout)
    except Exception as exc:
        log.warning("scrapegraphai error", url=url, error=str(exc))

    # Fallback: einfaches HTML-Parsing
    return await _fallback_extract(url)


async def _fallback_extract(url: str) -> ContactResult:
    """Einfaches HTTP + BeautifulSoup Parsing als Fallback."""
    import re
    try:
        import httpx
        from bs4 import BeautifulSoup

        EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
        NAME_RE  = re.compile(
            r"(?:Inhaber|Inhaberin|Geschäftsführer(?:in)?|Kontakt|Chef(?:in)?|Eigentümer(?:in)?)"
            r"\s*[:\-]?\s*([A-ZÄÖÜ][a-zäöü]+\s+[A-ZÄÖÜ][a-zäöüß\-]+)",
            re.MULTILINE,
        )
        base   = url.rstrip("/")
        pages  = [base, base + "/kontakt", base + "/contact", base + "/ueber-uns"]
        email  = vorname = nachname = ""

        async with httpx.AsyncClient(timeout=10, follow_redirects=True,
                                     verify=False) as client:
            for page in pages:
                try:
                    r    = await client.get(page, headers={"User-Agent": "Mozilla/5.0"})
                    soup = BeautifulSoup(r.text, "lxml")
                    text = soup.get_text(" ")

                    if not email:
                        for m in EMAIL_RE.findall(text):
                            if not any(s in m.lower() for s in ("noreply", "example", "test@")):
                                email = m; break

                    if not vorname:
                        m2 = NAME_RE.search(text)
                        if m2:
                            parts   = m2.group(1).split()
                            vorname = parts[0]
                            nachname = " ".join(parts[1:])

                    if email and vorname:
                        break
                except Exception:
                    continue

        return ContactResult(
            email=email, vorname=vorname, nachname=nachname,
            source_url=url, method="fallback",
        )
    except Exception as exc:
        log.debug("fallback_extract failed", url=url, error=str(exc))
        return ContactResult(source_url=url, method="fallback")


async def batch_extract_contacts(
    urls: list[str],
    concurrency: int = 3,
) -> list[ContactResult]:
    """
    Extrahiert Kontaktdaten für mehrere URLs parallel (max. `concurrency` gleichzeitig).
    """
    sem = asyncio.Semaphore(concurrency)

    async def _one(url: str) -> ContactResult:
        async with sem:
            return await extract_contact(url)

    return await asyncio.gather(*[_one(u) for u in urls])
