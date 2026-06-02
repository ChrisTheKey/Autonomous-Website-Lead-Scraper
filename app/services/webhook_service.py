"""
Outbound webhook service.

Delivers signed JSON payloads to registered endpoints on lead status changes.
Webhooks are HMAC-SHA256 signed using WEBHOOK_SECRET for receiver verification.

Webhook endpoints are stored in Redis as a sorted set.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any

import httpx
import structlog

from app.config import settings

log = structlog.get_logger()

_REDIS_WEBHOOKS_KEY = "webhooks:endpoints"


class WebhookEvent(str, Enum):
    lead_verified = "lead.verified"
    lead_rejected = "lead.rejected"
    lead_contacted = "lead.contacted"
    lead_suppressed = "lead.suppressed"
    export_created = "export.created"
    search_completed = "search.completed"
    ai_analysis_completed = "ai_analysis.completed"


@dataclass
class WebhookEndpoint:
    url: str
    events: list[str]
    active: bool = True


@dataclass
class WebhookDeliveryResult:
    url: str
    event: str
    success: bool
    status_code: int | None = None
    error: str | None = None


def _sign_payload(payload: bytes, secret: str) -> str:
    """Return HMAC-SHA256 hex signature for the payload."""
    return hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()


def _build_payload(event: WebhookEvent, data: dict[str, Any]) -> dict[str, Any]:
    return {
        "event": event.value,
        "timestamp": int(time.time()),
        "data": data,
    }


async def _deliver(url: str, event: WebhookEvent, payload: dict[str, Any]) -> WebhookDeliveryResult:
    """Send a single webhook delivery with retry (max 3 attempts)."""
    body = json.dumps(payload, default=str).encode()
    signature = _sign_payload(body, settings.webhook_secret) if settings.webhook_secret else ""

    headers = {
        "Content-Type": "application/json",
        "X-Lead-Scraper-Event": event.value,
        "X-Lead-Scraper-Signature": f"sha256={signature}",
        "X-Lead-Scraper-Timestamp": str(payload["timestamp"]),
    }

    async with httpx.AsyncClient(timeout=10) as client:
        for attempt in range(3):
            try:
                resp = await client.post(url, content=body, headers=headers)
                if resp.status_code < 300:
                    log.info("webhook.delivered", url=url, event=event.value, status=resp.status_code)
                    return WebhookDeliveryResult(url=url, event=event.value, success=True, status_code=resp.status_code)
                log.warning("webhook.bad_status", url=url, status=resp.status_code, attempt=attempt + 1)
            except httpx.RequestError as e:
                log.warning("webhook.request_error", url=url, error=str(e), attempt=attempt + 1)
                if attempt == 2:
                    return WebhookDeliveryResult(url=url, event=event.value, success=False, error=str(e))
            await _sleep(2 ** attempt)

    return WebhookDeliveryResult(url=url, event=event.value, success=False, error="max_retries_exceeded")


async def _sleep(seconds: float) -> None:
    import asyncio
    await asyncio.sleep(seconds)


# ── In-memory endpoint registry (production: replace with DB/Redis) ───────────

_ENDPOINTS: list[WebhookEndpoint] = []


def register_endpoint(url: str, events: list[str]) -> None:
    """Register a webhook endpoint. Idempotent by URL."""
    for ep in _ENDPOINTS:
        if ep.url == url:
            ep.events = events
            ep.active = True
            return
    _ENDPOINTS.append(WebhookEndpoint(url=url, events=events))
    log.info("webhook.endpoint_registered", url=url, events=events)


def unregister_endpoint(url: str) -> None:
    global _ENDPOINTS
    _ENDPOINTS = [ep for ep in _ENDPOINTS if ep.url != url]
    log.info("webhook.endpoint_unregistered", url=url)


def list_endpoints() -> list[WebhookEndpoint]:
    return list(_ENDPOINTS)


async def fire(event: WebhookEvent, data: dict[str, Any]) -> list[WebhookDeliveryResult]:
    """Fire an event to all registered, active endpoints that subscribe to it."""
    import asyncio

    payload = _build_payload(event, data)
    targets = [ep for ep in _ENDPOINTS if ep.active and (not ep.events or event.value in ep.events)]

    if not targets:
        return []

    tasks = [_deliver(ep.url, event, payload) for ep in targets]
    return await asyncio.gather(*tasks)


# ── Convenience helpers called from API handlers ───────────────────────────────

async def on_lead_verified(company_id: int, company_name: str) -> None:
    await fire(WebhookEvent.lead_verified, {"company_id": company_id, "company_name": company_name})


async def on_lead_rejected(company_id: int, company_name: str) -> None:
    await fire(WebhookEvent.lead_rejected, {"company_id": company_id, "company_name": company_name})


async def on_lead_contacted(company_id: int, company_name: str) -> None:
    await fire(WebhookEvent.lead_contacted, {"company_id": company_id, "company_name": company_name})


async def on_export_created(record_count: int, filename: str) -> None:
    await fire(WebhookEvent.export_created, {"record_count": record_count, "filename": filename})
