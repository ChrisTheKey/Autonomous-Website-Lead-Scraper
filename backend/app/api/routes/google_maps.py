from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.ai.maps_client import search_businesses, geocode_address

router = APIRouter()


class BusinessSearchRequest(BaseModel):
    query: str
    location: str
    radius_meters: int = 5000


@router.post("/business-search")
async def business_search(payload: BusinessSearchRequest) -> dict:
    results = await search_businesses(payload.query, payload.location, payload.radius_meters)
    return {"results": results}


@router.get("/geocode")
async def geocode(address: str = Query(...)) -> dict:
    coords = await geocode_address(address)
    return coords
