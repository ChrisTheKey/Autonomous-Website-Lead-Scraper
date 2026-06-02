"""
Review actions: verify, reject, mark-contacted, suppress, refresh, crawl, analyse, ai-analyse.
Each action writes an audit log entry.
"""

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.company import Company
from app.schemas.company import CompanyOut
from app.services.ai_service import AICompanyAnalysis, analyse_company
from app.services.email_validation_service import EmailValidationResult, validate_email
from app.services.compliance_service import (
    add_to_suppression,
    mark_contacted,
    mark_rejected,
    mark_verified,
)
from app.services.crm_service import CRMProvider, CRMSyncResult, push_company_to_crm
from app.services.webhook_service import on_lead_contacted, on_lead_rejected, on_lead_verified
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
    await on_lead_verified(company.id, company.name)
    return company


@router.post("/reject", response_model=CompanyOut)
async def reject_company(company_id: int, db: AsyncSession = Depends(get_db)) -> Company:
    company = await _get_or_404(company_id, db)
    await mark_rejected(company, db)
    await db.commit()
    await db.refresh(company)
    await on_lead_rejected(company.id, company.name)
    return company


@router.post("/mark-contacted", response_model=CompanyOut)
async def mark_company_contacted(company_id: int, db: AsyncSession = Depends(get_db)) -> Company:
    company = await _get_or_404(company_id, db)
    await mark_contacted(company, db)
    await db.commit()
    await db.refresh(company)
    await on_lead_contacted(company.id, company.name)
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


@router.post("/ai-analyse")
async def ai_analyse_company(company_id: int, db: AsyncSession = Depends(get_db)) -> AICompanyAnalysis:
    company = await _get_or_404(company_id, db)
    analysis = await analyse_company(
        company_name=company.name,
        industry=company.industry,
        location=company.location,
        website=company.website,
        phone=company.phone,
        website_signals={
            "has_https": company.has_https,
            "has_mobile_viewport": company.has_mobile_viewport,
            "has_contact_page": company.has_contact_page,
            "website_reachable": company.website_reachable,
        },
    )
    if analysis.opportunity_score > 0:
        company.website_opportunity_score = max(company.website_opportunity_score, analysis.opportunity_score)
        if not company.notes:
            company.notes = analysis.opportunity_summary
        await db.commit()
    return analysis


@router.post("/validate-email")
async def validate_company_email(
    company_id: int,
    email: str = Body(..., embed=True),
    smtp_probe: bool = Body(False, embed=True),
    db: AsyncSession = Depends(get_db),
) -> EmailValidationResult:
    await _get_or_404(company_id, db)
    import asyncio
    from functools import partial
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, partial(validate_email, email, smtp_probe))
    return result


@router.post("/crm-push")
async def crm_push_company(
    company_id: int,
    provider: CRMProvider = Body(..., embed=True),
    db: AsyncSession = Depends(get_db),
) -> CRMSyncResult:
    company = await _get_or_404(company_id, db)
    if not company.can_export:
        raise HTTPException(status_code=400, detail="Company is not exportable — verify it first")
    return await push_company_to_crm(company, provider)
