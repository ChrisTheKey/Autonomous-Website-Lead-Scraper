from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, HttpUrl
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.lead import Lead, LeadStatus

router = APIRouter()


class LeadCreate(BaseModel):
    company_name: str
    website: HttpUrl
    email: str | None = None
    phone: str | None = None
    address: str | None = None
    city: str | None = None
    country: str | None = None


class LeadOut(BaseModel):
    id: int
    company_name: str
    website: str
    email: str | None
    phone: str | None
    status: LeadStatus
    ai_summary: str | None
    crm_id: str | None
    crm_source: str | None

    model_config = {"from_attributes": True}


@router.get("/", response_model=list[LeadOut])
async def list_leads(
    status: LeadStatus | None = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
) -> list[Lead]:
    q = select(Lead).limit(limit).offset(offset)
    if status:
        q = q.where(Lead.status == status)
    result = await db.execute(q)
    return list(result.scalars().all())


@router.post("/", response_model=LeadOut, status_code=201)
async def create_lead(payload: LeadCreate, db: AsyncSession = Depends(get_db)) -> Lead:
    lead = Lead(**payload.model_dump())
    db.add(lead)
    await db.commit()
    await db.refresh(lead)
    return lead


@router.get("/{lead_id}", response_model=LeadOut)
async def get_lead(lead_id: int, db: AsyncSession = Depends(get_db)) -> Lead:
    lead = await db.get(Lead, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return lead


@router.delete("/{lead_id}", status_code=204)
async def delete_lead(lead_id: int, db: AsyncSession = Depends(get_db)) -> None:
    lead = await db.get(Lead, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    await db.delete(lead)
    await db.commit()
