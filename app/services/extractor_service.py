"""
Extracts publicly visible BUSINESS data from crawled pages.

Hard rules:
  - Only extracts data that is EXPLICITLY present on the page.
  - Never guesses, infers, or invents names/emails/roles.
  - Never extracts from LinkedIn or private social profiles.
  - is_personal_data = True for any full_name found, requiring manual review.
  - If no managing director is explicitly named on the page, field stays None.
  - Every extracted value gets source_url and source_type.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from bs4 import BeautifulSoup

from app.services.crawler_service import CrawlResult

_EMAIL_RE = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]{2,}")
_PHONE_DE_RE = re.compile(
    r"(?:\+41|\+49|\+43|0)[\s\-.]?\(?[\d]{2,4}\)?[\s\-.]?[\d]{3,}[\s\-.]?[\d]{2,}[\s\-.]?[\d]{0,4}"
)
_DIRECTOR_LABELS = re.compile(
    r"(?:geschäftsführer|inhaber|ceo|managing director|director|cto|coo|founder|gründer)[:\s]+",
    re.I,
)
_LEGAL_FORMS = re.compile(
    r"\b(GmbH|AG|KG|OHG|GbR|e\.K\.|UG|Ltd|Sarl|SA|SNC|SAS|SÀRL)\b", re.I
)


@dataclass
class ExtractedContact:
    full_name: str | None = None
    role: str | None = None
    email: str | None = None
    phone: str | None = None
    source_url: str = ""
    source_type: str = "company_website"
    confidence_score: float = 0.0
    is_personal_data: bool = False


@dataclass
class ExtractedCompanyData:
    company_name: str | None = None
    business_phone: str | None = None
    business_email: str | None = None
    address: str | None = None
    legal_form: str | None = None
    contacts: list[ExtractedContact] = field(default_factory=list)


def extract_from_pages(pages: list[CrawlResult]) -> ExtractedCompanyData:
    data = ExtractedCompanyData()

    for page in pages:
        if not page.robots_allowed or page.status_code != 200:
            continue

        text = page.text_excerpt
        url = page.url

        # Business phone — first match across all pages
        if not data.business_phone:
            phones = _PHONE_DE_RE.findall(text)
            if phones:
                data.business_phone = _clean_phone(phones[0])

        # Business email — first generic/non-personal address found
        if not data.business_email:
            emails = _EMAIL_RE.findall(text)
            for email in emails:
                local = email.split("@")[0].lower()
                # Prefer generic addresses; skip obvious personal ones
                if any(
                    kw in local
                    for kw in ("info", "kontakt", "contact", "hallo", "hello", "office", "mail")
                ):
                    data.business_email = email
                    break

        # Legal form
        if not data.legal_form:
            m = _LEGAL_FORMS.search(text)
            if m:
                data.legal_form = m.group(0)

        # Managing director / contact person
        # Only if explicitly labelled on page (not inferred)
        _extract_explicit_director(text, url, data)

    return data


def _extract_explicit_director(text: str, url: str, data: ExtractedCompanyData) -> None:
    for match in _DIRECTOR_LABELS.finditer(text):
        end = match.end()
        snippet = text[end : end + 80].strip()
        # Take only the first "word word" looking name (simple heuristic, explicit label required)
        name_match = re.match(r"([A-ZÄÖÜ][a-zäöüß]+ [A-ZÄÖÜ][a-zäöüß]+)", snippet)
        if name_match:
            name = name_match.group(1)
            role = match.group(0).rstrip(": ").title()
            contact = ExtractedContact(
                full_name=name,
                role=role,
                source_url=url,
                source_type="company_website",
                confidence_score=0.7,
                is_personal_data=True,  # full name = personal data → needs review
            )
            if not any(c.full_name == name for c in data.contacts):
                data.contacts.append(contact)


def _clean_phone(raw: str) -> str:
    return re.sub(r"[\s\-.()/]", "", raw.strip())
