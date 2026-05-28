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

import re
import unicodedata

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.company import Company
from app.services.compliance_service import write_audit


def normalize_name(name: str) -> str:
    # Lowercase, strip accents, remove legal suffixes, collapse whitespace
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    name = re.sub(r"\b(gmbh|ag|kg|ohg|gbr|ug|sarl|sa|ltd|e\.k\.)\b", "", name, flags=re.I)
    return re.sub(r"\s+", " ", name).strip().lower()


def normalize_phone(phone: str | None) -> str | None:
    if not phone:
        return None
    # Strip all non-digit characters except leading +
    digits = re.sub(r"[^\d+]", "", phone)
    if not digits:
        return None
    # Normalise Swiss/German/Austrian numbers
    if digits.startswith("0041"):
        digits = "+41" + digits[4:]
    elif digits.startswith("0049"):
        digits = "+49" + digits[4:]
    elif digits.startswith("0043"):
        digits = "+43" + digits[4:]
    return digits


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
