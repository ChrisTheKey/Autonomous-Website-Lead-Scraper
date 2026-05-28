"""
Orchestrates a full search run:
  1. Google Places API search
  2. Classification (no_website / weak / exists)
  3. Deduplication
  4. Company + PlaceCandidate persistence
  5. Scoring
  6. Optional: trigger website crawl for weak candidates
"""

from __future__ import annotations

from datetime import datetime, timezone

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.company import Company
from app.models.enums import CompanyStatus, EnrichmentStatus, LeadSourceType
from app.models.place_candidate import PlaceCandidate
from app.models.search import Search
from app.services.compliance_service import evaluate_can_export, write_audit
from app.services.dedupe_service import (
    find_duplicate,
    merge_into,
    normalize_name,
    normalize_phone,
)
from app.services.places_service import PlaceResult, search_places
from app.services.scoring_service import ScoreInput, calculate_score
from app.services.website_detection_service import classify_from_place, normalize_domain

log = structlog.get_logger()


async def run_search(search: Search, db: AsyncSession) -> int:
    """Execute one search and return number of new companies created."""
    search.status = "running"
    await db.flush()

    radius_m = search.radius_km * 1000
    places = await search_places(
        industry=search.industry,
        location=search.location,
        radius_m=radius_m,
        keywords=search.keywords or [],
        max_results=search.max_results,
    )

    created = 0
    for place in places:
        if place.business_status != "OPERATIONAL":
            continue  # skip non-operational businesses

        lead_type, enrichment_status, weak_reason = classify_from_place(place)

        # Skip "website_exists_not_target" if search targets no_website only
        if search.target == "no_website" and lead_type.value == "website_exists_not_target":
            continue

        company_data = {
            "name": place.name,
            "normalized_name": normalize_name(place.name),
            "industry": search.industry,
            "location": search.location,
            "address": place.formatted_address or None,
            "phone": normalize_phone(place.phone) or None,
            "website": place.website_uri or None,
            "normalized_domain": normalize_domain(place.website_uri),
            "google_place_id": place.place_id,
            "website_available": place.has_website,
            "lead_type": lead_type,
            "lead_source_type": LeadSourceType.google_places,
            "enrichment_status": enrichment_status,
            "status": CompanyStatus.needs_review,
            "data_origin": "google_places_api",
            "google_data_expires_at": place.expires_at,
            "data_retention_until": place.expires_at,
            "weak_website_reason": weak_reason,
        }

        existing = await find_duplicate(company_data, db)
        if existing:
            await merge_into(existing, company_data, db)
            company = existing
        else:
            company = Company(
                search_id=search.id,
                **company_data,
            )
            db.add(company)
            await db.flush()
            created += 1

        # Score
        score_input = ScoreInput(
            lead_type=lead_type,
            status=company.status,
            has_phone=bool(place.phone),
            has_address=bool(place.formatted_address),
            business_status_operational=(place.business_status == "OPERATIONAL"),
            industry_relevant=True,
            has_own_domain=not place.is_social_only,
            on_suppression_list=False,
            source_verified=True,
        )
        score, priority = calculate_score(score_input)
        company.website_opportunity_score = score
        company.lead_priority = priority

        # Compliance gate
        can_export, reason = await evaluate_can_export(company, db)
        company.can_export = can_export
        company.export_block_reason = reason

        # Persist place_candidate
        candidate = PlaceCandidate(
            search_id=search.id,
            company_id=company.id,
            google_place_id=place.place_id,
            has_website=place.has_website,
            website_uri=place.website_uri,
            phone_available=bool(place.phone),
            address_available=bool(place.formatted_address),
            business_status=place.business_status,
            types=place.types,
            rating=place.rating,
            user_rating_count=place.user_rating_count,
            raw_payload_hash=place.payload_hash,
            expires_at=place.expires_at,
        )
        db.add(candidate)

        await write_audit(db, "company", company.id, "discovered", metadata={"search_id": search.id})

    search.status = "completed"
    log.info("search_complete", search_id=search.id, created=created, total=len(places))
    return created
