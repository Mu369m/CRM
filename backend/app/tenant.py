"""Tenant resolution and PostgreSQL schema isolation helpers."""

import re
from uuid import UUID

from fastapi import Header, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from .models import TenantSettings

_SCHEMA_RE = re.compile(r"^tenant_[0-9a-f]{8}_[0-9a-f]{4}_[0-9a-f]{4}_[0-9a-f]{4}_[0-9a-f]{12}$")


def tenant_from_host(host: str) -> UUID | None:
    """Resolve a UUID subdomain while rejecting arbitrary SQL/schema identifiers."""
    label = host.split(":", 1)[0].split(".", 1)[0]
    try:
        return UUID(label)
    except ValueError:
        return None


async def resolve_tenant_settings(host: str = Header(default=""), db: AsyncSession | None = None) -> TenantSettings:
    """Load tenant settings by UUID host; production routing should also validate CNAME ownership."""
    tenant_id = tenant_from_host(host)
    if not tenant_id or db is None:
        raise HTTPException(status_code=400, detail="A valid tenant host is required")
    settings = await db.get(TenantSettings, tenant_id)
    if not settings:
        raise HTTPException(status_code=404, detail="Tenant configuration not found")
    return settings


async def set_tenant_search_path(db: AsyncSession, tenant_schema: str) -> None:
    """Set a transaction-local search path only after validating the stored schema name."""
    if not _SCHEMA_RE.fullmatch(tenant_schema):
        raise ValueError("Invalid tenant schema identifier")
    await db.execute(text(f'SET LOCAL search_path TO "{tenant_schema}", public'))
