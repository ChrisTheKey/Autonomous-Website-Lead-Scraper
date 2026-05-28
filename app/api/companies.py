from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.company import Company
from app.models.enums import CompanyStatus, LeadPriority, LeadType
from app.schemas.company import CompanyListOut, CompanyOut, CompanyUpdateNotes

router = APIRouter()


@router.get("/companies", response_model=list[CompanyListOut])
async def list_companies(
    lead_type: LeadType | None = Query(None),
    status: CompanyStatus | None = Query(None),
    priority: LeadPriority | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> list[Company]:
    q = select(Company).order_by(Company.website_opportunity_score.desc())
    if lead_type:
        q = q.where(Company.lead_type == lead_type)
    if status:
        q = q.where(Company.status == status)
    if priority:
        q = q.where(Company.lead_priority == priority)
    q = q.limit(limit).offset(offset)
    result = await db.execute(q)
    return list(result.scalars().all())


@router.get("/companies/{company_id}", response_model=CompanyOut)
async def get_company(company_id: int, db: AsyncSession = Depends(get_db)) -> Company:
    company = await db.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return company


@router.patch("/companies/{company_id}/notes", response_model=CompanyOut)
async def update_notes(
    company_id: int,
    payload: CompanyUpdateNotes,
    db: AsyncSession = Depends(get_db),
) -> Company:
    company = await db.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    company.notes = payload.notes
    await db.commit()
    await db.refresh(company)
    return company


@router.delete("/companies/{company_id}", status_code=204)
async def delete_company(company_id: int, db: AsyncSession = Depends(get_db)) -> None:
    company = await db.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    from app.services.compliance_service import write_audit
    await write_audit(db, "company", company_id, "deleted")
    await db.delete(company)
    await db.commit()
