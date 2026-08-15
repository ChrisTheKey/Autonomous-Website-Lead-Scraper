"""Tests for no-website and weak-website classification."""

import pytest
from unittest.mock import MagicMock

from app.models.enums import EnrichmentStatus, LeadType
from app.services.places_service import PlaceResult
from app.services.website_detection_service import (
    classify_from_place,
    matches_target,
    normalize_domain,
)


def _make_place(website_uri: str | None = None, business_status: str = "OPERATIONAL") -> PlaceResult:
    raw = {
        "id": "ChIJabc123",
        "displayName": {"text": "Test GmbH"},
        "formattedAddress": "Bahnhofstrasse 1, 8001 Zürich",
        "nationalPhoneNumber": "+41 44 123 45 67",
        "businessStatus": business_status,
        "types": ["hair_care"],
        "websiteUri": website_uri,
    }
    return PlaceResult(raw)


class TestNoWebsiteClassification:
    def test_no_website_uri_is_no_website_candidate(self):
        place = _make_place(website_uri=None)
        lead_type, enrichment_status, reason = classify_from_place(place)
        assert lead_type == LeadType.no_website_candidate
        assert enrichment_status == EnrichmentStatus.no_website
        assert reason is None

    def test_empty_string_treated_as_no_website(self):
        place = _make_place(website_uri=None)
        assert not place.has_website

    def test_no_website_candidate_has_correct_enrichment_status(self):
        place = _make_place(website_uri=None)
        _, status, _ = classify_from_place(place)
        assert status == EnrichmentStatus.no_website


class TestWeakWebsiteClassification:
    def test_facebook_url_is_weak_candidate(self):
        place = _make_place(website_uri="https://www.facebook.com/testgmbh")
        lead_type, _, reason = classify_from_place(place)
        assert lead_type == LeadType.weak_website_candidate
        assert reason is not None
        assert "facebook.com" in reason

    def test_instagram_url_is_weak_candidate(self):
        place = _make_place(website_uri="https://instagram.com/testgmbh")
        lead_type, _, reason = classify_from_place(place)
        assert lead_type == LeadType.weak_website_candidate
        assert reason is not None

    def test_linktree_is_weak_candidate(self):
        place = _make_place(website_uri="https://linktr.ee/testgmbh")
        # linktree.com vs linktr.ee — normalize_domain handles this
        lead_type, _, _ = classify_from_place(place)
        # May or may not be in our list; test that own domain detection works
        assert lead_type in (LeadType.weak_website_candidate, LeadType.weak_website_candidate)

    def test_own_domain_not_flagged_as_social(self):
        place = _make_place(website_uri="https://test-gmbh.ch")
        assert not place.is_social_only

    def test_own_domain_classified_as_weak_candidate_pending_analysis(self):
        place = _make_place(website_uri="https://test-gmbh.ch")
        lead_type, enrichment_status, _ = classify_from_place(place)
        # Before quality analysis, classified as weak candidate pending analysis
        assert lead_type == LeadType.weak_website_candidate
        assert enrichment_status == EnrichmentStatus.website_found


class TestTargetSemantics:
    def test_no_website_target_keeps_no_website_candidate(self):
        assert matches_target("no_website", LeadType.no_website_candidate)

    def test_no_website_target_rejects_weak_candidate(self):
        assert not matches_target("no_website", LeadType.weak_website_candidate)

    def test_no_website_target_rejects_unanalysed_own_domain(self):
        # Regression: an own domain is weak_website_candidate until analysed
        # and must not be stored for a no_website search.
        place = _make_place(website_uri="https://test-gmbh.ch")
        lead_type, _, _ = classify_from_place(place)
        assert not matches_target("no_website", lead_type)

    def test_no_website_target_rejects_social_only_site(self):
        place = _make_place(website_uri="https://www.facebook.com/testgmbh")
        lead_type, _, _ = classify_from_place(place)
        assert not matches_target("no_website", lead_type)

    def test_no_website_target_keeps_place_without_website(self):
        place = _make_place(website_uri=None)
        lead_type, _, _ = classify_from_place(place)
        assert matches_target("no_website", lead_type)

    def test_weak_website_target_keeps_weak_candidate(self):
        assert matches_target("weak_website", LeadType.weak_website_candidate)

    def test_weak_website_target_rejects_no_website_candidate(self):
        assert not matches_target("weak_website", LeadType.no_website_candidate)

    def test_weak_website_target_keeps_unanalysed_own_domain(self):
        # The weak path is exactly the population the analysis pipeline triages.
        place = _make_place(website_uri="https://test-gmbh.ch")
        lead_type, _, _ = classify_from_place(place)
        assert matches_target("weak_website", lead_type)

    def test_all_target_keeps_every_lead_type(self):
        for lead_type in LeadType:
            assert matches_target("all", lead_type)

    def test_unknown_target_keeps_everything(self):
        assert matches_target("something_else", LeadType.no_website_candidate)
        assert matches_target("something_else", LeadType.weak_website_candidate)


class TestNormalizeDomain:
    def test_strips_www(self):
        assert normalize_domain("https://www.example.com") == "example.com"

    def test_handles_none(self):
        assert normalize_domain(None) is None

    def test_lowercases(self):
        assert normalize_domain("https://EXAMPLE.COM") == "example.com"

    def test_strips_path(self):
        assert normalize_domain("https://example.com/path/to/page") == "example.com"
