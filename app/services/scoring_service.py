"""
Calculates website_opportunity_score (0–100) and lead_priority.

Scoring rules mirror the spec exactly. All logic is deterministic
and unit-testable without a database.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.models.enums import CompanyStatus, LeadPriority, LeadType


@dataclass
class ScoreInput:
    lead_type: LeadType
    status: CompanyStatus
    has_phone: bool
    has_address: bool
    business_status_operational: bool
    industry_relevant: bool
    # Website quality signals (for weak_website_candidate)
    has_own_domain: bool = True
    has_https: bool = True
    website_reachable: bool = True
    has_mobile_viewport: bool = True
    has_contact_page: bool = True
    is_construction_page: bool = False
    # Suppression
    on_suppression_list: bool = False
    # Source
    source_verified: bool = True


def calculate_score(inp: ScoreInput) -> tuple[int, LeadPriority]:
    # Hard blocks
    if inp.on_suppression_list:
        return 0, LeadPriority.blocked
    if not inp.source_verified:
        return max(0, 0 - 50), LeadPriority.blocked

    score = 0

    if inp.lead_type == LeadType.no_website_candidate:
        score += 40  # no website
        if inp.has_phone:
            score += 20
        if inp.has_address:
            score += 15
        if inp.business_status_operational:
            score += 15
        if inp.industry_relevant:
            score += 10

    elif inp.lead_type == LeadType.weak_website_candidate:
        if not inp.has_own_domain:
            score += 35
        if not inp.has_https:
            score += 15
        if not inp.website_reachable or inp.is_construction_page:
            score += 25
        if not inp.has_mobile_viewport:
            score += 15
        if not inp.has_contact_page:
            score += 10
        # Penalise if website is actually fine
        if inp.has_own_domain and inp.has_https and inp.has_mobile_viewport and inp.has_contact_page:
            score -= 60

    else:
        # website_exists_not_target or invalid
        return 0, LeadPriority.low_priority

    # Status penalties
    if inp.status == CompanyStatus.contacted:
        score -= 40
    if inp.status == CompanyStatus.rejected:
        score -= 80

    score = max(0, min(100, score))

    if score >= 70:
        priority = LeadPriority.high_priority
    elif score >= 40:
        priority = LeadPriority.medium_priority
    else:
        priority = LeadPriority.low_priority

    return score, priority
