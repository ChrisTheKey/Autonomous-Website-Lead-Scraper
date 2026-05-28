"""
Classifies companies by website status.

Classification logic:
  1. No website_uri from Google Places → no_website_candidate
  2. website_uri points to a social/platform domain → weak_website_candidate (no_own_website)
  3. website_uri is an own domain → proceed to quality analysis
"""

from __future__ import annotations

from urllib.parse import urlparse

from app.models.enums import EnrichmentStatus, LeadType
from app.services.places_service import PlaceResult, _SOCIAL_DOMAINS


def classify_from_place(place: PlaceResult) -> tuple[LeadType, EnrichmentStatus, str | None]:
    """
    Returns (lead_type, enrichment_status, weak_website_reason).
    """
    if not place.has_website:
        return LeadType.no_website_candidate, EnrichmentStatus.no_website, None

    if place.is_social_only:
        host = urlparse(place.website_uri or "").hostname or ""
        return (
            LeadType.weak_website_candidate,
            EnrichmentStatus.website_found,
            f"no_own_website:{host}",
        )

    return LeadType.weak_website_candidate, EnrichmentStatus.website_found, None


def normalize_domain(url: str | None) -> str | None:
    if not url:
        return None
    parsed = urlparse(url if url.startswith("http") else f"https://{url}")
    host = parsed.hostname or ""
    # strip www.
    return host.removeprefix("www.").lower() or None


def is_social_domain(url: str) -> bool:
    host = urlparse(url if url.startswith("http") else f"https://{url}").hostname or ""
    host = host.removeprefix("www.")
    return any(host == d or host.endswith("." + d) for d in _SOCIAL_DOMAINS)
