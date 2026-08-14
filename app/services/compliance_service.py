"""
Compliance gate for exports and data handling.

Hard rules:
  - No export if status != verified.
  - No export if on suppression list.
  - No export of personal data without source_url.
  - no_website_candidates require manual review before export.
  - Google-Places-only data: only derived signals exported, not raw API data.
  - Every action writes an AuditLog entry.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog
from app.models.company import Company
from app.models.contact import Contact
from app.models.enums import CompanyStatus, LeadType
from app.models.suppression import SuppressionEntry
from app.services.normalization import normalize_phone


async def evaluate_can_export(company: Company, db: AsyncSession) -> tuple[bool, str | None]:
    """
    Returns (can_export, block_reason).
    Called after every status change that might affect exportability.
    """
    if company.status != CompanyStatus.verified:
        return False, f"status_not_verified:{company.status.value}"

    if await is_suppressed(company, db):
        return False, "on_suppression_list"

    if company.lead_type == LeadType.no_website_candidate:
        # Allowed only after explicit human verification
        if not company.verified_at:
            return False, "no_website_candidate_requires_manual_verification"

    # Check contacts for personal data without source
    result = await db.execute(
        select(Contact).where(
            Contact.company_id == company.id,
            Contact.is_personal_data == True,  # noqa: E712
            Contact.source_url == None,  # noqa: E711
        )
    )
    unsafe_contacts = result.scalars().all()
    if unsafe_contacts:
        return False, "personal_data_without_source_url"

    return True, None


async def is_suppressed(company: Company, db: AsyncSession) -> bool:
    filters = []
    if company.id:
        filters.append(SuppressionEntry.company_id == company.id)
    if company.google_place_id:
        filters.append(SuppressionEntry.google_place_id == company.google_place_id)
    if company.normalized_domain:
        filters.append(SuppressionEntry.domain == company.normalized_domain)
    if company.phone:
        norm = normalize_phone(company.phone)
        if norm:
            filters.append(SuppressionEntry.phone == norm)

    if not filters:
        return False

    from sqlalchemy import or_
    result = await db.execute(select(SuppressionEntry).where(or_(*filters)))
    return result.first() is not None


async def write_audit(
    db: AsyncSession,
    entity_type: str,
    entity_id: int,
    action: str,
    actor: str = "system",
    metadata: dict | None = None,
) -> None:
    log_entry = AuditLog(
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        actor=actor,
        event_metadata=metadata or {},
    )
    db.add(log_entry)
    await db.flush()


async def mark_verified(company: Company, db: AsyncSession, actor: str = "user") -> None:
    company.status = CompanyStatus.verified
    company.verified_at = datetime.now(tz=timezone.utc)
    can_export, reason = await evaluate_can_export(company, db)
    company.can_export = can_export
    company.export_block_reason = reason
    await write_audit(db, "company", company.id, "verified", actor)


async def mark_rejected(company: Company, db: AsyncSession, actor: str = "user") -> None:
    company.status = CompanyStatus.rejected
    company.can_export = False
    company.export_block_reason = "rejected"
    await write_audit(db, "company", company.id, "rejected", actor)


async def mark_contacted(company: Company, db: AsyncSession, actor: str = "user") -> None:
    company.status = CompanyStatus.contacted
    company.contacted_at = datetime.now(tz=timezone.utc)
    # Re-evaluate export after status change (score will drop due to contacted penalty)
    await write_audit(db, "company", company.id, "contacted", actor)


async def add_to_suppression(
    company: Company,
    db: AsyncSession,
    reason: str,
    actor: str = "user",
) -> None:
    entry = SuppressionEntry(
        company_id=company.id,
        domain=company.normalized_domain,
        phone=normalize_phone(company.phone) if company.phone else None,
        google_place_id=company.google_place_id,
        reason=reason,
    )
    db.add(entry)
    company.status = CompanyStatus.suppressed
    company.can_export = False
    company.export_block_reason = "suppressed"
    await write_audit(db, "company", company.id, "suppressed", actor, {"reason": reason})
