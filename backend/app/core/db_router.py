"""BYODB engine cache and tenant session dependency."""

import asyncio
from collections import OrderedDict
from collections.abc import AsyncIterator
from urllib.parse import urlsplit
from uuid import UUID

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from ..crypto import decrypt_field
from ..db import SessionFactory
from ..models.master import BrokerTenant
from ..security import current_claims

_MAX_CACHED_ENGINES = 100
_engines: OrderedDict[UUID, AsyncEngine] = OrderedDict()
_engine_locks: dict[UUID, asyncio.Lock] = {}
_cache_lock = asyncio.Lock()


def validate_database_url(database_url: str) -> str:
    """Accept only PostgreSQL async URLs and reject embedded query surprises."""
    parsed = urlsplit(database_url)
    if parsed.scheme not in {"postgresql+asyncpg", "postgresql"} or not parsed.hostname:
        raise ValueError("Only PostgreSQL connection URLs are supported")
    if parsed.fragment:
        raise ValueError("Database URL fragments are not allowed")
    return database_url.replace("postgresql://", "postgresql+asyncpg://", 1)


async def get_tenant_engine(tenant: BrokerTenant) -> AsyncEngine:
    """Reuse a bounded engine cache and serialize first connection creation per tenant."""
    tenant_id = tenant.id
    async with _cache_lock:
        cached = _engines.get(tenant_id)
        if cached:
            _engines.move_to_end(tenant_id)
            return cached
        lock = _engine_locks.setdefault(tenant_id, asyncio.Lock())
    async with lock:
        async with _cache_lock:
            cached = _engines.get(tenant_id)
            if cached:
                _engines.move_to_end(tenant_id)
                return cached
        database_url = validate_database_url(decrypt_field(tenant.encrypted_db_url or ""))
        engine = create_async_engine(database_url, pool_pre_ping=True, pool_size=5, max_overflow=10, pool_recycle=1800)
        async with _cache_lock:
            _engines[tenant_id] = engine
            _engines.move_to_end(tenant_id)
            while len(_engines) > _MAX_CACHED_ENGINES:
                _, evicted = _engines.popitem(last=False)
                await evicted.dispose()
        return engine


async def close_tenant_engines() -> None:
    """Dispose all private pools during application shutdown."""
    async with _cache_lock:
        engines = list(_engines.values())
        _engines.clear()
    await asyncio.gather(*(engine.dispose() for engine in engines))


async def invalidate_tenant_engine(tenant_id: UUID) -> None:
    """Dispose one cached pool after a broker changes its private database URL."""
    async with _cache_lock:
        engine = _engines.pop(tenant_id, None)
    if engine:
        await engine.dispose()


async def get_tenant_db(
    claims: dict[str, str] = Depends(current_claims),
    x_tenant_id: str | None = Header(default=None),
    host: str = Header(default=""),
) -> AsyncIterator[AsyncSession]:
    """Yield a private session only when header, JWT, and master registry agree."""
    try:
        claim_tenant = UUID(claims["tenant_id"])
        requested_tenant = UUID(x_tenant_id) if x_tenant_id else claim_tenant
    except (KeyError, ValueError) as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid tenant identity") from error
    if requested_tenant != claim_tenant:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant identity mismatch")
    async with SessionFactory() as master_db:
        broker = await master_db.get(BrokerTenant, claim_tenant)
    if not broker or not broker.is_active or not broker.encrypted_db_url:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Private tenant database is not configured")
    request_host = host.split(":", 1)[0].lower()
    allowed_hosts = {broker.subdomain.lower()}
    if broker.custom_domain:
        allowed_hosts.add(broker.custom_domain.lower())
    if request_host and request_host not in {"localhost", "127.0.0.1"} and request_host not in allowed_hosts:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant host does not match authenticated tenant")
    engine = await get_tenant_engine(broker)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
