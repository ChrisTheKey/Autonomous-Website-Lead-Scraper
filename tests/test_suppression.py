"""Tests for suppression list matching."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.compliance_service import is_suppressed


def _company(google_place_id=None, normalized_domain=None, phone=None, company_id=1):
    c = MagicMock()
    c.id = company_id
    c.google_place_id = google_place_id
    c.normalized_domain = normalized_domain
    c.phone = phone
    return c


class TestSuppressionList:
    @pytest.mark.asyncio
    async def test_no_identifiers_returns_not_suppressed(self):
        company = _company(google_place_id=None, normalized_domain=None, phone=None)
        db = AsyncMock()
        result = await is_suppressed(company, db)
        assert not result

    @pytest.mark.asyncio
    async def test_match_on_place_id_returns_suppressed(self):
        company = _company(google_place_id="ChIJabc123")
        db = AsyncMock()
        db.execute = AsyncMock(return_value=MagicMock(first=MagicMock(return_value=("row",))))
        result = await is_suppressed(company, db)
        assert result

    @pytest.mark.asyncio
    async def test_no_match_returns_not_suppressed(self):
        company = _company(google_place_id="ChIJabc123")
        db = AsyncMock()
        db.execute = AsyncMock(return_value=MagicMock(first=MagicMock(return_value=None)))
        result = await is_suppressed(company, db)
        assert not result
