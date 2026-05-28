"""
Google Places API (New) integration.

Uses only the official API — no scraping, no unofficial endpoints.
Stores only what is needed: place_id, classification metadata, and
a hash of the raw payload for audit purposes.

Per Google Maps Platform Terms of Service:
  - Data is fetched fresh on demand or via refresh.
  - expires_at is set to settings.google_data_ttl_days from fetch time.
  - We store place_id and our own derived signals; raw API payloads
    are NOT persisted in the database.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

import httpx
import structlog

from app.config import settings

log = structlog.get_logger()

# Social/platform domains that indicate no own website
_SOCIAL_DOMAINS = frozenset(
    [
        "facebook.com", "fb.com", "instagram.com", "twitter.com", "x.com",
        "linkedin.com", "tiktok.com", "youtube.com", "pinterest.com",
        "linktree.com", "bio.link", "beacons.ai", "taplink.cc",
        "sites.google.com", "wixsite.com", "weebly.com", "jimdo.com",
        "my.canva.site",
    ]
)

_FIELD_MASK = ",".join([
    "places.id",
    "places.displayName",
    "places.formattedAddress",
    "places.nationalPhoneNumber",
    "places.internationalPhoneNumber",
    "places.businessStatus",
    "places.types",
    "places.rating",
    "places.userRatingCount",
    "places.websiteUri",
])


class PlaceResult:
    def __init__(self, raw: dict) -> None:
        self.place_id: str = raw.get("id", "")
        display = raw.get("displayName", {})
        self.name: str = display.get("text", "") if isinstance(display, dict) else str(display)
        self.formatted_address: str = raw.get("formattedAddress", "")
        self.phone: str = raw.get("nationalPhoneNumber", "") or raw.get("internationalPhoneNumber", "")
        self.business_status: str = raw.get("businessStatus", "")
        self.types: list[str] = raw.get("types", [])
        self.rating: float | None = raw.get("rating")
        self.user_rating_count: int | None = raw.get("userRatingCount")
        self.website_uri: str | None = raw.get("websiteUri")
        self._raw = raw

    @property
    def has_website(self) -> bool:
        return bool(self.website_uri)

    @property
    def is_social_only(self) -> bool:
        if not self.website_uri:
            return False
        host = urlparse(self.website_uri).hostname or ""
        return any(host == d or host.endswith("." + d) for d in _SOCIAL_DOMAINS)

    @property
    def payload_hash(self) -> str:
        return hashlib.sha256(json.dumps(self._raw, sort_keys=True).encode()).hexdigest()

    @property
    def expires_at(self) -> datetime:
        return datetime.now(tz=timezone.utc) + timedelta(days=settings.google_data_ttl_days)


async def search_places(
    industry: str,
    location: str,
    radius_m: int,
    keywords: list[str] | None = None,
    max_results: int = 100,
) -> list[PlaceResult]:
    query = industry
    if keywords:
        query += " " + " ".join(keywords)

    results: list[PlaceResult] = []
    next_page_token: str | None = None

    async with httpx.AsyncClient(timeout=15) as client:
        while len(results) < max_results:
            payload: dict = {
                "textQuery": f"{query} in {location}",
                "locationBias": {
                    "circle": {
                        "center": await _geocode_location(location, client),
                        "radius": float(radius_m),
                    }
                },
                "pageSize": min(20, max_results - len(results)),
                "languageCode": "de",
            }
            if next_page_token:
                payload["pageToken"] = next_page_token

            response = await client.post(
                f"{settings.google_places_base_url}/places:searchText",
                headers={
                    "X-Goog-Api-Key": settings.google_maps_api_key,
                    "X-Goog-FieldMask": _FIELD_MASK,
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

            for place_data in data.get("places", []):
                results.append(PlaceResult(place_data))

            next_page_token = data.get("nextPageToken")
            if not next_page_token:
                break

    log.info("places_search_complete", query=query, location=location, count=len(results))
    return results[:max_results]


async def refresh_place(place_id: str) -> PlaceResult | None:
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.get(
            f"{settings.google_places_base_url}/places/{place_id}",
            headers={
                "X-Goog-Api-Key": settings.google_maps_api_key,
                "X-Goog-FieldMask": _FIELD_MASK.replace("places.", ""),
            },
        )
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return PlaceResult(response.json())


async def _geocode_location(location: str, client: httpx.AsyncClient) -> dict:
    resp = await client.get(
        "https://maps.googleapis.com/maps/api/geocode/json",
        params={"address": location, "key": settings.google_maps_api_key},
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("results"):
        loc = data["results"][0]["geometry"]["location"]
        return {"latitude": loc["lat"], "longitude": loc["lng"]}
    return {"latitude": 47.3769, "longitude": 8.5417}  # Zürich fallback
