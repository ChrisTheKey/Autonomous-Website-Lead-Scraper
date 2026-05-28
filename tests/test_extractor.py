"""
Tests for the extractor service.

Critical invariant: extractor MUST NEVER invent a managing director.
It must only extract names explicitly labelled on the page.
"""

import pytest

from app.services.crawler_service import CrawlResult
from app.services.extractor_service import extract_from_pages


def _page(text: str, url: str = "https://example.com/impressum", status: int = 200) -> CrawlResult:
    return CrawlResult(url=url, status_code=status, title="Test", text_excerpt=text, robots_allowed=True)


class TestExtractorNeverInventsData:
    def test_no_director_label_produces_no_contact(self):
        page = _page("Muster GmbH — Wir sind ein Friseursalon in Zürich. Tel: +41441234567")
        result = extract_from_pages([page])
        assert result.contacts == []

    def test_explicit_director_label_extracts_name(self):
        page = _page("Geschäftsführer: Hans Müller — kontaktieren Sie uns per Telefon.")
        result = extract_from_pages([page])
        assert len(result.contacts) == 1
        assert result.contacts[0].full_name == "Hans Müller"
        assert result.contacts[0].is_personal_data is True

    def test_extracted_contact_has_source_url(self):
        page = _page("Inhaber: Maria Meier — unsere Adresse ist ...", url="https://example.com/impressum")
        result = extract_from_pages([page])
        if result.contacts:
            assert result.contacts[0].source_url == "https://example.com/impressum"

    def test_no_name_without_explicit_label(self):
        page = _page("Hans Müller liebt seinen Beruf als Coiffeur.")
        result = extract_from_pages([page])
        # Name appears but without a director-label → should NOT be extracted
        assert not any(c.full_name == "Hans Müller" for c in result.contacts)

    def test_no_email_guessing(self):
        """Extractor must only find emails that are literally on the page."""
        page = _page("Kontaktieren Sie uns telefonisch unter +41441234567.")
        result = extract_from_pages([page])
        assert result.business_email is None

    def test_generic_email_extracted(self):
        page = _page("Schreiben Sie uns: info@mustergmbh.ch — wir freuen uns.")
        result = extract_from_pages([page])
        assert result.business_email == "info@mustergmbh.ch"

    def test_personal_email_not_preferred(self):
        """hans.mueller@mustergmbh.ch should be deprioritised over info@."""
        page = _page(
            "info@mustergmbh.ch | hans.mueller@mustergmbh.ch"
        )
        result = extract_from_pages([page])
        assert result.business_email == "info@mustergmbh.ch"


class TestPhoneExtraction:
    def test_swiss_phone_extracted(self):
        page = _page("Telefon: +41 44 123 45 67")
        result = extract_from_pages([page])
        assert result.business_phone is not None

    def test_no_phone_on_page_returns_none(self):
        page = _page("Wir haben keine Kontaktinformationen auf dieser Seite.")
        result = extract_from_pages([page])
        assert result.business_phone is None


class TestRobotsRespect:
    def test_disallowed_page_not_extracted(self):
        page = CrawlResult(
            url="https://example.com/admin",
            status_code=200,
            title="Admin",
            text_excerpt="Geschäftsführer: Max Muster",
            robots_allowed=False,
        )
        result = extract_from_pages([page])
        assert result.contacts == []
        assert result.business_phone is None
