"""
Analytics & reporting endpoints.

GET /analytics/overview          – counts by status and lead type
GET /analytics/lead-aging        – how long leads sit in each state
GET /analytics/top-industries    – top industries by lead count
GET /analytics/search-performance – search runs with result counts
GET /analytics/ai-score-histogram – distribution of opportunity scores
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.company import Company
from app.models.enums import CompanyStatus
from app.models.search import Search

router = APIRouter(prefix="/analytics", tags=["analytics"])

DbDep = Annotated[AsyncSession, Depends(get_db)]


class StatusCounts(BaseModel):
    status: str
    count: int


class LeadTypeCounts(BaseModel):
    lead_type: str
    count: int


class IndustryCounts(BaseModel):
    industry: str | None
    count: int


class SearchPerformance(BaseModel):
    id: int
    industry: str | None
    location: str | None
    status: str
    max_results: int
    created_at: str | None


class ScoreBucket(BaseModel):
    bucket: str
    count: int


class AnalyticsOverview(BaseModel):
    total_companies: int
    by_status: list[StatusCounts]
    by_lead_type: list[LeadTypeCounts]
    exportable: int
    suppressed: int


@router.get("/overview", response_model=AnalyticsOverview)
async def get_overview(db: DbDep) -> AnalyticsOverview:
    total_result = await db.execute(select(func.count(Company.id)))
    total = total_result.scalar() or 0

    status_result = await db.execute(
        select(Company.status, func.count(Company.id)).group_by(Company.status)
    )
    by_status = [StatusCounts(status=row[0].value, count=row[1]) for row in status_result.all()]

    type_result = await db.execute(
        select(Company.lead_type, func.count(Company.id)).group_by(Company.lead_type)
    )
    by_lead_type = [
        LeadTypeCounts(lead_type=row[0].value if row[0] else "unknown", count=row[1])
        for row in type_result.all()
    ]

    exportable_result = await db.execute(
        select(func.count(Company.id)).where(Company.can_export.is_(True))
    )
    exportable = exportable_result.scalar() or 0

    suppressed_result = await db.execute(
        select(func.count(Company.id)).where(Company.status == CompanyStatus.suppressed)
    )
    suppressed = suppressed_result.scalar() or 0

    return AnalyticsOverview(
        total_companies=total,
        by_status=by_status,
        by_lead_type=by_lead_type,
        exportable=exportable,
        suppressed=suppressed,
    )


@router.get("/top-industries", response_model=list[IndustryCounts])
async def top_industries(limit: int = 20, db: DbDep = Depends(get_db)) -> list[IndustryCounts]:
    result = await db.execute(
        select(Company.industry, func.count(Company.id).label("cnt"))
        .group_by(Company.industry)
        .order_by(func.count(Company.id).desc())
        .limit(limit)
    )
    return [IndustryCounts(industry=row[0], count=row[1]) for row in result.all()]


@router.get("/search-performance", response_model=list[SearchPerformance])
async def search_performance(limit: int = 50, db: DbDep = Depends(get_db)) -> list[SearchPerformance]:
    result = await db.execute(
        select(Search).order_by(Search.created_at.desc()).limit(limit)
    )
    runs = result.scalars().all()
    return [
        SearchPerformance(
            id=r.id,
            industry=r.industry,
            location=r.location,
            status=r.status,
            max_results=r.max_results,
            created_at=r.created_at.isoformat() if r.created_at else None,
        )
        for r in runs
    ]


@router.get("/ai-score-histogram", response_model=list[ScoreBucket])
async def score_histogram(db: DbDep = Depends(get_db)) -> list[ScoreBucket]:
    result = await db.execute(select(Company.website_opportunity_score))
    scores = [row[0] for row in result.all() if row[0] is not None]

    buckets = {"0-20": 0, "21-40": 0, "41-60": 0, "61-80": 0, "81-100": 0}
    for s in scores:
        if s <= 20:
            buckets["0-20"] += 1
        elif s <= 40:
            buckets["21-40"] += 1
        elif s <= 60:
            buckets["41-60"] += 1
        elif s <= 80:
            buckets["61-80"] += 1
        else:
            buckets["81-100"] += 1

    return [ScoreBucket(bucket=k, count=v) for k, v in buckets.items()]
