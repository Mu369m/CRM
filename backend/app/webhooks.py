"""Signed provider webhook ingress with durable event deduplication."""

import json
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Request

from .config import get_settings
from .db import SessionFactory
from .events import persist_event, verify_hmac
from .worker import dispatch_automation

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


@router.post("/{provider}")
async def provider_webhook(provider: str, request: Request, x_signature: str = Header(default=""), x_event_id: str = Header(default="")):
    """Authenticate, persist, and asynchronously dispatch a provider event exactly once."""
    body = await request.body()
    settings = get_settings()
    if not x_event_id or not verify_hmac(body, x_signature, settings.webhook_signing_secret.get_secret_value()):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")
    payload = json.loads(body)
    tenant_id = UUID(payload["tenant_id"]) if payload.get("tenant_id") else None
    async with SessionFactory() as db:
        accepted = await persist_event(db, tenant_id, provider, x_event_id, body)
    if accepted:
        dispatch_automation.delay(f"{provider}.{payload.get('type', 'event')}", payload)
    return {"accepted": True, "duplicate": not accepted}
