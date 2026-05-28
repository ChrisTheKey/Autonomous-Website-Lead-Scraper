"""Tests for places_service — uses mocked HTTP, never calls real API."""

import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.places_service import PlaceResult, _SOCIAL_DOMAINS


def _raw_place(website_uri=None, business_status="OPERATIONAL", name="Test GmbH"):
    return {
        "id": "ChIJabc123",
        "displayName": {"text": name},
        "formattedAddress": "Bahnhofstrasse 1, 8001 Zürich",
        "nationalPhoneNumber": "+41 44 123 45 67",
        "businessStatus": business_status,
        "types": ["hair_care"],
        "websiteUri": website_uri,
    }


class TestPlaceResult:
    def test_name_extracted(self):
        p = PlaceResult(_raw_place(name="Coiffeur Müller GmbH"))
        assert p.name == "Coiffeur Müller GmbH"

    def test_has_website_false_when_none(self):
        p = PlaceResult(_raw_place(website_uri=None))
        assert not p.has_website

    def test_has_website_true_when_uri_present(self):
        p = PlaceResult(_raw_place(website_uri="https://example.ch"))
        assert p.has_website

    def test_is_social_only_false_for_own_domain(self):
        p = PlaceResult(_raw_place(website_uri="https://mein-coiffeur.ch"))
        assert not p.is_social_only

    def test_is_social_only_true_for_facebook(self):
        p = PlaceResult(_raw_place(website_uri="https://www.facebook.com/meincoiffeur"))
        assert p.is_social_only

    def test_is_social_only_true_for_instagram(self):
        p = PlaceResult(_raw_place(website_uri="https://instagram.com/meincoiffeur"))
        assert p.is_social_only

    def test_payload_hash_is_deterministic(self):
        raw = _raw_place()
        p1 = PlaceResult(raw)
        p2 = PlaceResult(raw)
        assert p1.payload_hash == p2.payload_hash

    def test_expires_at_in_future(self):
        from datetime import datetime, timezone
        p = PlaceResult(_raw_place())
        assert p.expires_at > datetime.now(tz=timezone.utc)

    def test_business_status_preserved(self):
        p = PlaceResult(_raw_place(business_status="CLOSED_PERMANENTLY"))
        assert p.business_status == "CLOSED_PERMANENTLY"


class TestSocialDomainSet:
    def test_facebook_in_set(self):
        assert "facebook.com" in _SOCIAL_DOMAINS

    def test_instagram_in_set(self):
        assert "instagram.com" in _SOCIAL_DOMAINS

    def test_own_domain_not_in_set(self):
        assert "mein-coiffeur.ch" not in _SOCIAL_DOMAINS
