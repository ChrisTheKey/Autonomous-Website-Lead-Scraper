"""Tests for website_opportunity_score calculation."""

import pytest

from app.models.enums import CompanyStatus, LeadPriority, LeadType
from app.services.scoring_service import ScoreInput, calculate_score


def _no_website_input(**kwargs) -> ScoreInput:
    defaults = dict(
        lead_type=LeadType.no_website_candidate,
        status=CompanyStatus.needs_review,
        has_phone=True,
        has_address=True,
        business_status_operational=True,
        industry_relevant=True,
        on_suppression_list=False,
        source_verified=True,
    )
    defaults.update(kwargs)
    return ScoreInput(**defaults)


class TestNoWebsiteScoring:
    def test_perfect_no_website_lead_scores_100(self):
        score, priority = calculate_score(_no_website_input())
        assert score == 100
        assert priority == LeadPriority.high_priority

    def test_no_phone_reduces_score(self):
        score, _ = calculate_score(_no_website_input(has_phone=False))
        assert score == 80

    def test_no_address_reduces_score(self):
        score, _ = calculate_score(_no_website_input(has_address=False))
        assert score == 85

    def test_not_operational_reduces_score(self):
        score, _ = calculate_score(_no_website_input(business_status_operational=False))
        assert score == 85

    def test_not_industry_relevant_reduces_score(self):
        score, _ = calculate_score(_no_website_input(industry_relevant=False))
        assert score == 90

    def test_contacted_reduces_score_dramatically(self):
        score, _ = calculate_score(_no_website_input(status=CompanyStatus.contacted))
        assert score == 60

    def test_suppressed_returns_zero_and_blocked(self):
        score, priority = calculate_score(_no_website_input(on_suppression_list=True))
        assert score == 0
        assert priority == LeadPriority.blocked

    def test_unverified_source_returns_blocked(self):
        score, priority = calculate_score(_no_website_input(source_verified=False))
        assert priority == LeadPriority.blocked


class TestWeakWebsiteScoring:
    def _weak_input(self, **kwargs) -> ScoreInput:
        defaults = dict(
            lead_type=LeadType.weak_website_candidate,
            status=CompanyStatus.needs_review,
            has_phone=True,
            has_address=True,
            business_status_operational=True,
            industry_relevant=True,
            has_own_domain=False,
            has_https=False,
            website_reachable=False,
            has_mobile_viewport=False,
            has_contact_page=False,
            is_construction_page=True,
            on_suppression_list=False,
            source_verified=True,
        )
        defaults.update(kwargs)
        return ScoreInput(**defaults)

    def test_all_weak_signals_score_high(self):
        score, priority = calculate_score(self._weak_input())
        assert score >= 70
        assert priority == LeadPriority.high_priority

    def test_modern_website_scores_low(self):
        score, priority = calculate_score(
            self._weak_input(
                has_own_domain=True,
                has_https=True,
                website_reachable=True,
                has_mobile_viewport=True,
                has_contact_page=True,
                is_construction_page=False,
            )
        )
        assert score < 40
        assert priority == LeadPriority.low_priority


class TestPriorityBuckets:
    def test_score_70_is_high_priority(self):
        _, priority = calculate_score(_no_website_input())
        assert priority == LeadPriority.high_priority

    def test_score_between_40_69_is_medium(self):
        score, priority = calculate_score(_no_website_input(has_phone=False, has_address=False))
        assert 40 <= score < 70
        assert priority == LeadPriority.medium_priority
