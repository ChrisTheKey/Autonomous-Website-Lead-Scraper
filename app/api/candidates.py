from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.place_candidate import PlaceCandidate
from app.models.enums import ReviewStatus
from pydantic import BaseModel
from datetime import datetime


class PlaceCandidateOut(BaseModel):
    id: int
    search_id: int
    company_id: int | None
    google_place_id: str
    has_website: bool
    website_uri: str | None
    phone_available: bool
    address_available: bool
    business_status: str | None
    types: list | None
    rating: float | None
    user_rating_count: int | None
    review_status: ReviewStatus
    fetched_at: datetime
    expires_at: datetime | None
    notes: str | None

    model_config = {"from_attributes": True}


router = APIRouter()


@router.get("/candidates", response_model=list[PlaceCandidateOut])
async def list_candidates(
    search_id: int | None = Query(None),
    has_website: bool | None = Query(None),
    review_status: ReviewStatus | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> list[PlaceCandidate]:
    q = select(PlaceCandidate).order_by(PlaceCandidate.fetched_at.desc())
    if search_id:
        q = q.where(PlaceCandidate.search_id == search_id)
    if has_website is not None:
        q = q.where(PlaceCandidate.has_website == has_website)
    if review_status:
        q = q.where(PlaceCandidate.review_status == review_status)
    q = q.limit(limit).offset(offset)
    result = await db.execute(q)
    return list(result.scalars().all())
