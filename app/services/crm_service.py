"""
CRM sync service for HubSpot, Salesforce, and Pipedrive.

Each integration follows the same contract:
  push_company(company) -> CRMSyncResult

Only verified, exportable leads are pushed (enforced by the caller).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any

import structlog

from app.config import settings

if TYPE_CHECKING:
    from app.models.company import Company

log = structlog.get_logger()


class CRMProvider(str, Enum):
    hubspot = "hubspot"
    salesforce = "salesforce"
    pipedrive = "pipedrive"


@dataclass
class CRMSyncResult:
    provider: CRMProvider
    success: bool
    external_id: str | None = None
    error: str | None = None


# ─── HubSpot ──────────────────────────────────────────────────────────────────

def _push_to_hubspot(company: "Company") -> CRMSyncResult:
    if not settings.hubspot_api_key:
        return CRMSyncResult(CRMProvider.hubspot, False, error="no_api_key")

    try:
        from hubspot import HubSpot
        from hubspot.crm.companies import SimplePublicObjectInputForCreate

        client = HubSpot(access_token=settings.hubspot_api_key)

        properties: dict[str, Any] = {
            "name": company.name,
            "phone": company.phone or "",
            "city": company.location or "",
            "industry": company.industry or "",
            "website": company.website or "",
            "description": f"Lead source: {company.lead_source_type.value}. Score: {company.website_opportunity_score}",
        }

        result = client.crm.companies.basic_api.create(
            simple_public_object_input_for_create=SimplePublicObjectInputForCreate(
                properties=properties
            )
        )
        log.info("crm.hubspot.pushed", company_id=company.id, hs_id=result.id)
        return CRMSyncResult(CRMProvider.hubspot, True, external_id=result.id)

    except Exception as e:
        log.error("crm.hubspot.error", company_id=company.id, error=str(e))
        return CRMSyncResult(CRMProvider.hubspot, False, error=str(e))


# ─── Salesforce ───────────────────────────────────────────────────────────────

def _push_to_salesforce(company: "Company") -> CRMSyncResult:
    if not settings.salesforce_username:
        return CRMSyncResult(CRMProvider.salesforce, False, error="no_credentials")

    try:
        from simple_salesforce import Salesforce

        sf = Salesforce(
            username=settings.salesforce_username,
            password=settings.salesforce_password,
            security_token=settings.salesforce_security_token,
            domain=settings.salesforce_domain,
        )

        result = sf.Account.create({
            "Name": company.name,
            "Phone": company.phone or "",
            "BillingCity": company.location or "",
            "Industry": company.industry or "",
            "Website": company.website or "",
            "Description": f"Lead Discovery Score: {company.website_opportunity_score}",
            "LeadSource": "Web Research",
        })

        sf_id = result.get("id")
        log.info("crm.salesforce.pushed", company_id=company.id, sf_id=sf_id)
        return CRMSyncResult(CRMProvider.salesforce, True, external_id=sf_id)

    except Exception as e:
        log.error("crm.salesforce.error", company_id=company.id, error=str(e))
        return CRMSyncResult(CRMProvider.salesforce, False, error=str(e))


# ─── Pipedrive ────────────────────────────────────────────────────────────────

def _push_to_pipedrive(company: "Company") -> CRMSyncResult:
    if not settings.pipedrive_api_token:
        return CRMSyncResult(CRMProvider.pipedrive, False, error="no_api_token")

    try:
        import httpx

        base_url = (
            f"https://{settings.pipedrive_domain}.pipedrive.com/api/v1"
            if settings.pipedrive_domain
            else "https://api.pipedrive.com/v1"
        )

        payload = {
            "name": company.name,
            "phone": [{"value": company.phone, "primary": True}] if company.phone else [],
            "address": company.address or "",
        }

        resp = httpx.post(
            f"{base_url}/organizations",
            params={"api_token": settings.pipedrive_api_token},
            json=payload,
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        pd_id = str(data.get("data", {}).get("id", ""))
        log.info("crm.pipedrive.pushed", company_id=company.id, pd_id=pd_id)
        return CRMSyncResult(CRMProvider.pipedrive, True, external_id=pd_id)

    except Exception as e:
        log.error("crm.pipedrive.error", company_id=company.id, error=str(e))
        return CRMSyncResult(CRMProvider.pipedrive, False, error=str(e))


# ─── Public interface ─────────────────────────────────────────────────────────

_PROVIDER_MAP = {
    CRMProvider.hubspot: _push_to_hubspot,
    CRMProvider.salesforce: _push_to_salesforce,
    CRMProvider.pipedrive: _push_to_pipedrive,
}


async def push_company_to_crm(company: "Company", provider: CRMProvider) -> CRMSyncResult:
    """Push a single company to the given CRM provider (async wrapper)."""
    import asyncio
    from functools import partial

    loop = asyncio.get_event_loop()
    fn = _PROVIDER_MAP[provider]
    return await loop.run_in_executor(None, partial(fn, company))


async def push_company_to_all_crms(company: "Company") -> list[CRMSyncResult]:
    """Push a company to all configured CRM providers."""
    import asyncio

    providers = []
    if settings.hubspot_api_key:
        providers.append(CRMProvider.hubspot)
    if settings.salesforce_username:
        providers.append(CRMProvider.salesforce)
    if settings.pipedrive_api_token:
        providers.append(CRMProvider.pipedrive)

    if not providers:
        log.warning("crm.no_providers_configured")
        return []

    tasks = [push_company_to_crm(company, p) for p in providers]
    return await asyncio.gather(*tasks)
