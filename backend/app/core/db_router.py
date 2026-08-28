"""BYODB engine cache and tenant session dependency."""

import asyncio
from collections import OrderedDict
from collections.abc import AsyncIterator
from urllib.parse import urlsplit
from uuid import UUID

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy import select

from ..config import get_settings
from ..crypto import decrypt_field
from ..db import SessionFactory
from ..models import Tenant
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


async def get_tenant_session_factories() -> list[tuple[UUID, async_sessionmaker[AsyncSession]]]:
    """Build tenant-scoped factories from the master registry for background workers."""
    async with SessionFactory() as master_db:
        brokers = list(await master_db.scalars(select(BrokerTenant).where(BrokerTenant.is_active.is_(True))))
        shared_tenants = list(await master_db.scalars(select(Tenant).where(Tenant.is_active.is_(True))))
    factories: list[tuple[UUID, async_sessionmaker[AsyncSession]]] = []
    broker_ids = {broker.id for broker in brokers}
    for broker in brokers:
        if broker.encrypted_db_url:
            engine = await get_tenant_engine(broker)
            factory = async_sessionmaker(engine, expire_on_commit=False)
        else:
            factory = SessionFactory
        factories.append((broker.id, factory))
    factories.extend((tenant.id, SessionFactory) for tenant in shared_tenants if tenant.id not in broker_ids)
    return factories


async def invalidate_tenant_engine(tenant_id: UUID) -> None:
    """Dispose one cached pool after a broker changes its private database URL."""
    async with _cache_lock:
        engine = _engines.pop(tenant_id, None)
    if engine:
        await engine.dispose()


async def get_tenant_db(
    claims: dict[str, str] = Depends(current_claims),
    x_tenant_id: str | None = Header(default=None),
    x_tenant_host: str | None = Header(default=None, alias="X-Tenant-Host"),
    host: str = Header(default=""),
) -> AsyncIterator[AsyncSession]:
    """Yield the tenant's private or shared-schema session after host validation."""
    try:
        claim_tenant = UUID(claims["tenant_id"])
        requested_tenant = UUID(x_tenant_id) if x_tenant_id else claim_tenant
    except (KeyError, ValueError) as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid tenant identity") from error
    if requested_tenant != claim_tenant:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant identity mismatch")
    async with SessionFactory() as master_db:
        broker = await master_db.get(BrokerTenant, claim_tenant)
        shared_tenant = await master_db.get(Tenant, claim_tenant) if not broker else None
    if not broker and not shared_tenant:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant is not configured or active")
    if (broker and not broker.is_active) or (shared_tenant and not shared_tenant.is_active):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant is not configured or active")
    request_host = (x_tenant_host or host).split(":", 1)[0].lower()
    allowed_hosts = set()
    if broker:
        allowed_hosts.add(broker.subdomain.lower())
        if broker.custom_domain:
            allowed_hosts.add(broker.custom_domain.lower())
    if shared_tenant:
        if shared_tenant.subdomain:
            allowed_hosts.add(shared_tenant.subdomain.lower())
        if shared_tenant.custom_domain:
            allowed_hosts.add(shared_tenant.custom_domain.lower())
    env = get_settings().environment
    if env == "production" and request_host and request_host not in {"localhost", "127.0.0.1"} and request_host not in allowed_hosts:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant host does not match authenticated tenant")
    factory = SessionFactory
    if broker and broker.encrypted_db_url:
        engine = await get_tenant_engine(broker)
        factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
