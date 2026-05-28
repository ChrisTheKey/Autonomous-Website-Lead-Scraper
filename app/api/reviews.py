"""
Review actions: verify, reject, mark-contacted, suppress, refresh, crawl, analyse.
Each action writes an audit log entry.
"""

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.company import Company
from app.schemas.company import CompanyOut
from app.services.compliance_service import (
    add_to_suppression,
    mark_contacted,
    mark_rejected,
    mark_verified,
)
from app.workers.tasks import (
    analyse_website_task,
    crawl_company_task,
    refresh_company_task,
)

router = APIRouter(prefix="/companies/{company_id}")


async def _get_or_404(company_id: int, db: AsyncSession) -> Company:
    company = await db.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return company


@router.post("/verify", response_model=CompanyOut)
async def verify_company(company_id: int, db: AsyncSession = Depends(get_db)) -> Company:
    company = await _get_or_404(company_id, db)
    await mark_verified(company, db)
    await db.commit()
    await db.refresh(company)
    return company


@router.post("/reject", response_model=CompanyOut)
async def reject_company(company_id: int, db: AsyncSession = Depends(get_db)) -> Company:
    company = await _get_or_404(company_id, db)
    await mark_rejected(company, db)
    await db.commit()
    await db.refresh(company)
    return company


@router.post("/mark-contacted", response_model=CompanyOut)
async def mark_company_contacted(company_id: int, db: AsyncSession = Depends(get_db)) -> Company:
    company = await _get_or_404(company_id, db)
    await mark_contacted(company, db)
    await db.commit()
    await db.refresh(company)
    return company


@router.post("/add-to-suppression", response_model=CompanyOut)
async def suppress_company(
    company_id: int,
    reason: str = Body(..., embed=True),
    db: AsyncSession = Depends(get_db),
) -> Company:
    company = await _get_or_404(company_id, db)
    await add_to_suppression(company, db, reason=reason)
    await db.commit()
    await db.refresh(company)
    return company


@router.post("/refresh")
async def refresh_company(company_id: int, db: AsyncSession = Depends(get_db)) -> dict:
    company = await _get_or_404(company_id, db)
    if not company.google_place_id:
        raise HTTPException(status_code=400, detail="No Google Place ID — cannot refresh")
    task = refresh_company_task.delay(company_id)
    return {"task_id": task.id, "status": "queued"}


@router.post("/crawl")
async def crawl_company(company_id: int, db: AsyncSession = Depends(get_db)) -> dict:
    company = await _get_or_404(company_id, db)
    if not company.website:
        raise HTTPException(status_code=400, detail="No website URL to crawl")
    task = crawl_company_task.delay(company_id)
    return {"task_id": task.id, "status": "queued"}


@router.post("/analyze-website")
async def analyze_website(company_id: int, db: AsyncSession = Depends(get_db)) -> dict:
    company = await _get_or_404(company_id, db)
    if not company.website:
        raise HTTPException(status_code=400, detail="No website to analyse")
    task = analyse_website_task.delay(company_id)
    return {"task_id": task.id, "status": "queued"}
