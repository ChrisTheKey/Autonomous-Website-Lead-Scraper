"""Tests for the compliance export gate."""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.enums import CompanyStatus, EnrichmentStatus, LeadSourceType, LeadType
from app.services.compliance_service import evaluate_can_export


def _make_company(**kwargs):
    company = MagicMock()
    company.id = 1
    company.status = CompanyStatus.verified
    company.lead_type = LeadType.no_website_candidate
    company.verified_at = datetime.now(tz=timezone.utc)
    company.google_place_id = "ChIJabc"
    company.normalized_domain = None
    company.phone = None
    for k, v in kwargs.items():
        setattr(company, k, v)
    return company


class TestComplianceExportGate:
    @pytest.mark.asyncio
    async def test_unverified_company_cannot_export(self):
        company = _make_company(status=CompanyStatus.needs_review)
        db = AsyncMock()
        can_export, reason = await evaluate_can_export(company, db)
        assert not can_export
        assert "status_not_verified" in reason

    @pytest.mark.asyncio
    async def test_rejected_company_cannot_export(self):
        company = _make_company(status=CompanyStatus.rejected)
        db = AsyncMock()
        can_export, reason = await evaluate_can_export(company, db)
        assert not can_export

    @pytest.mark.asyncio
    async def test_no_website_candidate_requires_verified_at(self):
        company = _make_company(
            status=CompanyStatus.verified,
            lead_type=LeadType.no_website_candidate,
            verified_at=None,
        )
        db = AsyncMock()
        # Suppress suppression check
        with patch("app.services.compliance_service.is_suppressed", return_value=False):
            # Contacts check
            from unittest.mock import patch as p2
            with p2("app.services.compliance_service.is_suppressed", new=AsyncMock(return_value=False)):
                db.execute = AsyncMock(return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))))
                can_export, reason = await evaluate_can_export(company, db)
        assert not can_export
        assert "manual_verification" in reason

    @pytest.mark.asyncio
    async def test_verified_company_with_verified_at_can_export(self):
        company = _make_company(
            status=CompanyStatus.verified,
            lead_type=LeadType.no_website_candidate,
            verified_at=datetime.now(tz=timezone.utc),
        )
        db = AsyncMock()
        db.execute = AsyncMock(
            return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[]))))
        )
        with patch("app.services.compliance_service.is_suppressed", new=AsyncMock(return_value=False)):
            can_export, reason = await evaluate_can_export(company, db)
        assert can_export
        assert reason is None

    @pytest.mark.asyncio
    async def test_suppressed_company_cannot_export(self):
        company = _make_company(status=CompanyStatus.verified)
        db = AsyncMock()
        with patch("app.services.compliance_service.is_suppressed", new=AsyncMock(return_value=True)):
            can_export, reason = await evaluate_can_export(company, db)
        assert not can_export
        assert "suppression" in reason
