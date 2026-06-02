"""
Bulk / batch operations on companies.

POST /batch/verify       – verify multiple companies at once
POST /batch/reject       – reject multiple companies
POST /batch/suppress     – add multiple companies to suppression list
POST /batch/export       – export a filtered set of companies to CSV
POST /batch/ai-analyse   – run Claude AI analysis on multiple companies
POST /batch/crm-push     – push multiple companies to a CRM
"""

from __future__ import annotations

import csv
import io
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.company import Company
from app.models.enums import CompanyStatus
from app.services.compliance_service import write_audit
from app.services.crm_service import CRMProvider, push_company_to_crm
from app.services.webhook_service import on_lead_rejected, on_lead_verified

router = APIRouter(prefix="/batch", tags=["batch"])

DbDep = Annotated[AsyncSession, Depends(get_db)]


class BatchIDRequest(BaseModel):
    company_ids: list[int]


class BatchSuppressRequest(BaseModel):
    company_ids: list[int]
    reason: str = "bulk_suppression"


class BatchCRMRequest(BaseModel):
    company_ids: list[int]
    provider: CRMProvider


class BatchResult(BaseModel):
    processed: int
    failed: int
    errors: list[str] = []


@router.post("/verify", response_model=BatchResult)
async def batch_verify(req: BatchIDRequest, db: DbDep) -> BatchResult:
    """Verify multiple companies in one call."""
    processed = 0
    errors: list[str] = []

    result = await db.execute(select(Company).where(Company.id.in_(req.company_ids)))
    companies = result.scalars().all()

    for company in companies:
        try:
            company.status = CompanyStatus.verified
            company.can_export = True
            await write_audit(db, "company", company.id, "batch_verify")
            await on_lead_verified(company.id, company.name)
            processed += 1
        except Exception as e:
            errors.append(f"company {company.id}: {e}")

    return BatchResult(processed=processed, failed=len(errors), errors=errors)


@router.post("/reject", response_model=BatchResult)
async def batch_reject(req: BatchIDRequest, db: DbDep) -> BatchResult:
    processed = 0
    errors: list[str] = []

    result = await db.execute(select(Company).where(Company.id.in_(req.company_ids)))
    companies = result.scalars().all()

    for company in companies:
        try:
            company.status = CompanyStatus.rejected
            company.can_export = False
            await write_audit(db, "company", company.id, "batch_reject")
            await on_lead_rejected(company.id, company.name)
            processed += 1
        except Exception as e:
            errors.append(f"company {company.id}: {e}")

    return BatchResult(processed=processed, failed=len(errors), errors=errors)


@router.post("/suppress", response_model=BatchResult)
async def batch_suppress(req: BatchSuppressRequest, db: DbDep) -> BatchResult:
    from app.models.enums import CompanyStatus
    from app.models.suppression import SuppressionEntry

    processed = 0
    errors: list[str] = []

    result = await db.execute(select(Company).where(Company.id.in_(req.company_ids)))
    companies = result.scalars().all()

    for company in companies:
        try:
            company.status = CompanyStatus.suppressed
            company.can_export = False
            entry = SuppressionEntry(
                entry_type="company_name",
                value=company.normalized_name or company.name,
                reason=req.reason,
                source="batch_operation",
            )
            db.add(entry)
            await write_audit(db, "company", company.id, "batch_suppress", metadata={"reason": req.reason})
            processed += 1
        except Exception as e:
            errors.append(f"company {company.id}: {e}")

    return BatchResult(processed=processed, failed=len(errors), errors=errors)


@router.post("/ai-analyse", response_model=BatchResult)
async def batch_ai_analyse(req: BatchIDRequest, db: DbDep) -> BatchResult:
    """Run Claude AI analysis on multiple companies."""
    from app.services.ai_service import analyse_company

    result = await db.execute(select(Company).where(Company.id.in_(req.company_ids)))
    companies = result.scalars().all()

    processed = 0
    errors: list[str] = []

    for company in companies:
        try:
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
                company.website_opportunity_score = max(
                    company.website_opportunity_score, analysis.opportunity_score
                )
                if not company.notes:
                    company.notes = analysis.opportunity_summary
            await write_audit(
                db, "company", company.id, "ai_analyse",
                metadata={"score": analysis.opportunity_score, "summary": analysis.opportunity_summary}
            )
            processed += 1
        except Exception as e:
            errors.append(f"company {company.id}: {e}")

    return BatchResult(processed=processed, failed=len(errors), errors=errors)


@router.post("/crm-push", response_model=BatchResult)
async def batch_crm_push(req: BatchCRMRequest, db: DbDep) -> BatchResult:
    """Push multiple verified companies to a CRM."""
    result = await db.execute(
        select(Company).where(
            Company.id.in_(req.company_ids),
            Company.can_export.is_(True),
        )
    )
    companies = result.scalars().all()

    if not companies:
        raise HTTPException(status_code=400, detail="No exportable companies found in the provided IDs")

    processed = 0
    errors: list[str] = []

    for company in companies:
        crm_result = await push_company_to_crm(company, req.provider)
        if crm_result.success:
            await write_audit(
                db, "company", company.id, "crm_push",
                metadata={"provider": req.provider.value, "external_id": crm_result.external_id}
            )
            processed += 1
        else:
            errors.append(f"company {company.id}: {crm_result.error}")

    return BatchResult(processed=processed, failed=len(errors), errors=errors)
