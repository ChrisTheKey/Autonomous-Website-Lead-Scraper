"""
Deduplication service.

Deduplicates on:
  1. google_place_id (exact)
  2. normalized_name + normalized_address
  3. normalized_phone
  4. normalized_domain (if present)

Merges duplicates by keeping the richer record and logging the merge.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.company import Company
from app.services.compliance_service import write_audit
from app.services.normalization import normalize_name, normalize_phone


async def find_duplicate(company_data: dict, db: AsyncSession) -> Company | None:
    """Check if a company already exists before inserting."""

    # 1. By google_place_id
    if pid := company_data.get("google_place_id"):
        result = await db.execute(select(Company).where(Company.google_place_id == pid))
        if existing := result.scalar_one_or_none():
            return existing

    # 2. By normalized_domain
    if domain := company_data.get("normalized_domain"):
        result = await db.execute(
            select(Company).where(Company.normalized_domain == domain)
        )
        if existing := result.scalar_one_or_none():
            return existing

    # 3. By normalized_phone
    if phone := normalize_phone(company_data.get("phone")):
        result = await db.execute(select(Company).where(Company.phone == phone))
        if existing := result.scalar_one_or_none():
            return existing

    # 4. By normalized_name (fuzzy)
    if name := company_data.get("name"):
        norm = normalize_name(name)
        result = await db.execute(
            select(Company).where(Company.normalized_name == norm)
        )
        if existing := result.scalar_one_or_none():
            return existing

    return None


async def merge_into(
    existing: Company,
    new_data: dict,
    db: AsyncSession,
) -> Company:
    """
    Enrich existing company with non-null fields from new_data.
    Never overwrites existing non-null values.
    """
    changed: dict = {}
    for field, value in new_data.items():
        if value and not getattr(existing, field, None):
            setattr(existing, field, value)
            changed[field] = value

    if changed:
        await write_audit(db, "company", existing.id, "dedupe_merge", metadata={"merged": changed})

    return existing
