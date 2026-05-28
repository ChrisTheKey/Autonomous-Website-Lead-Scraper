"""
Google Maps integration via googlemaps/google-maps-services-python.
Used for geocoding addresses and searching nearby businesses.
"""

import asyncio
from functools import partial

import googlemaps

from app.core.config import settings

_gmaps = googlemaps.Client(key=settings.google_maps_api_key)


def _run_sync(fn, *args, **kwargs):
    loop = asyncio.get_event_loop()
    return loop.run_in_executor(None, partial(fn, *args, **kwargs))


async def geocode_address(address: str) -> dict:
    results = await _run_sync(_gmaps.geocode, address)
    if not results:
        return {"lat": None, "lng": None, "formatted": address}
    loc = results[0]["geometry"]["location"]
    return {
        "lat": loc["lat"],
        "lng": loc["lng"],
        "formatted": results[0]["formatted_address"],
    }


async def search_businesses(query: str, location: str, radius: int = 5000) -> list[dict]:
    geo = await geocode_address(location)
    if not geo["lat"]:
        return []

    results = await _run_sync(
        _gmaps.places,
        query=query,
        location=(geo["lat"], geo["lng"]),
        radius=radius,
    )

    businesses = []
    for place in results.get("results", []):
        details_raw = await _run_sync(_gmaps.place, place_id=place["place_id"])
        details = details_raw.get("result", {})
        businesses.append(
            {
                "name": details.get("name"),
                "address": details.get("formatted_address"),
                "phone": details.get("formatted_phone_number"),
                "website": details.get("website"),
                "rating": details.get("rating"),
                "lat": details.get("geometry", {}).get("location", {}).get("lat"),
                "lng": details.get("geometry", {}).get("location", {}).get("lng"),
                "place_id": place["place_id"],
            }
        )
    return businesses
