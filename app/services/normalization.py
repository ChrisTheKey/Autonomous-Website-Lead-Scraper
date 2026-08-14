"""
Pure normalisation helpers for company identity fields.

Dependency-free by design: both dedupe_service (to find duplicates) and
compliance_service (to match suppression entries) need these, so they must
not live in either module.
"""

from __future__ import annotations

import re
import unicodedata


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
