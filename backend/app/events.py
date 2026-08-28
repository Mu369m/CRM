"""Reliable webhook event intake primitives."""

import hashlib
import hmac
import json
from uuid import UUID

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from .models import WebhookEvent


def verify_hmac(body: bytes, signature: str, secret: str) -> bool:
    """Compare provider signatures in constant time to prevent timing leaks."""
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature.removeprefix("sha256="))


async def persist_event(
    db: AsyncSession, tenant_id: UUID | None, provider: str, event_id: str, body: bytes
) -> bool:
    """Insert once; duplicate provider event IDs become harmless no-op retries."""
    statement = insert(WebhookEvent).values(
        tenant_id=tenant_id, provider=provider, event_id=event_id,
        payload=json.loads(body),
    ).on_conflict_do_nothing(index_elements=["provider", "event_id"])
    result = await db.execute(statement)
    await db.commit()
    return result.rowcount == 1
