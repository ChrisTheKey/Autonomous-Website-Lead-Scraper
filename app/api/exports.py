from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.database import get_db
from app.models.enums import LeadType
from app.services.export_service import export_verified_csv
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


@router.get("/export")
async def export_leads(
    lead_type: LeadType | None = Query(None, description="Filter by lead type"),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    csv_data = await export_verified_csv(db, lead_type=lead_type)
    await db.commit()

    filename = "leads_verified.csv"
    if lead_type == LeadType.no_website_candidate:
        filename = "no_website_candidates.csv"

    return StreamingResponse(
        iter([csv_data]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/export/no-website-candidates")
async def export_no_website(db: AsyncSession = Depends(get_db)) -> StreamingResponse:
    csv_data = await export_verified_csv(db, lead_type=LeadType.no_website_candidate)
    await db.commit()
    return StreamingResponse(
        iter([csv_data]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=no_website_candidates.csv"},
    )
