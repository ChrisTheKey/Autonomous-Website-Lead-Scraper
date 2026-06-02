"""
Webhook management endpoints.

GET    /webhooks           – list registered endpoints
POST   /webhooks           – register a new endpoint
DELETE /webhooks/{url}     – remove an endpoint
POST   /webhooks/test      – send a test event to all endpoints
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, HttpUrl

from app.services.webhook_service import (
    WebhookDeliveryResult,
    WebhookEndpoint,
    WebhookEvent,
    fire,
    list_endpoints,
    register_endpoint,
    unregister_endpoint,
)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


class RegisterWebhookRequest(BaseModel):
    url: HttpUrl
    events: list[str] = []


class WebhookEndpointResponse(BaseModel):
    url: str
    events: list[str]
    active: bool


@router.get("", response_model=list[WebhookEndpointResponse])
async def get_webhooks() -> list[WebhookEndpointResponse]:
    return [
        WebhookEndpointResponse(url=ep.url, events=ep.events, active=ep.active)
        for ep in list_endpoints()
    ]


@router.post("", response_model=WebhookEndpointResponse, status_code=201)
async def create_webhook(req: RegisterWebhookRequest) -> WebhookEndpointResponse:
    url = str(req.url)
    register_endpoint(url, req.events)
    return WebhookEndpointResponse(url=url, events=req.events, active=True)


@router.delete("/{url:path}", status_code=204)
async def delete_webhook(url: str) -> None:
    unregister_endpoint(url)


@router.post("/test", response_model=list[WebhookDeliveryResult])
async def test_webhooks() -> list[WebhookDeliveryResult]:
    """Send a test event to all registered endpoints."""
    return await fire(
        WebhookEvent.lead_verified,
        {"company_id": 0, "company_name": "Test Company", "test": True},
    )
