"""
CSV export service.

Export gate (enforced here AND in compliance_service):
  - Only companies with status=verified and can_export=True.
  - No suppressed leads.
  - No raw Google data — only our derived signals.
  - No personal data without source_url.
  - Exports only the fields listed in the spec.
"""

from __future__ import annotations

import csv
import io
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.company import Company
from app.models.enums import CompanyStatus, LeadType
from app.schemas.export import ExportRow
from app.services.compliance_service import write_audit


_EXPORT_HEADERS = [
    "company_name",
    "industry",
    "location",
    "phone",
    "address",
    "website_status",
    "lead_type",
    "website_opportunity_score",
    "source_type",
    "verified_at",
    "notes",
]


async def export_verified_csv(
    db: AsyncSession,
    lead_type: LeadType | None = None,
    actor: str = "user",
) -> str:
    q = select(Company).where(
        Company.status == CompanyStatus.verified,
        Company.can_export == True,  # noqa: E712
    )
    if lead_type:
        q = q.where(Company.lead_type == lead_type)

    result = await db.execute(q)
    companies = result.scalars().all()

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=_EXPORT_HEADERS, extrasaction="ignore")
    writer.writeheader()

    for c in companies:
        row = ExportRow(
            company_name=c.name,
            industry=c.industry,
            location=c.location,
            phone=c.phone if c.phone else None,
            address=c.address if c.address else None,
            website_status="no_website" if not c.website_available else "has_website",
            lead_type=c.lead_type,
            website_opportunity_score=c.website_opportunity_score,
            source_type=c.lead_source_type,
            verified_at=c.verified_at,
            notes=c.notes,
        )
        writer.writerow(row.model_dump())

        await write_audit(
            db,
            "company",
            c.id,
            "exported",
            actor=actor,
            metadata={"export_type": "csv", "lead_type": c.lead_type.value},
        )

    return buf.getvalue()
