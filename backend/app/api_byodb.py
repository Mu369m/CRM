"""Broker BYODB onboarding endpoint."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from .byodb_schemas import TenantDatabasePayload, TenantDatabaseResponse
from .crypto import encrypt_field
from .db import get_db
from .models import Role
from .models.master import BrokerTenant
from .security import require_roles
from .core.db_router import invalidate_tenant_engine, validate_database_url
from .core.tenant_migrations import migrate_tenant_database
from .core.cloud_provisioner import create_digitalocean_postgres

router = APIRouter(prefix="/api/v1/admin/settings", tags=["BYODB"])


@router.put("/database", response_model=TenantDatabaseResponse)
async def configure_private_database(
    payload: TenantDatabasePayload,
    claims: dict[str, str] = Depends(require_roles(Role.BROKER_ADMIN, Role.SUPER_ADMIN)),
    master_db: AsyncSession = Depends(get_db),
) -> TenantDatabaseResponse:
    """Verify, migrate, and register a broker-owned PostgreSQL database."""
    tenant_id = UUID(claims["tenant_id"])
    database_url = validate_database_url(payload.database_url.get_secret_value())
    test_engine = create_async_engine(database_url, pool_pre_ping=True, pool_size=1, max_overflow=0)
    try:
        async with test_engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        await migrate_tenant_database(database_url)
        broker = await master_db.get(BrokerTenant, tenant_id)
        if not broker:
            broker = BrokerTenant(id=tenant_id, company_name="Broker", subdomain=str(tenant_id), encrypted_db_url=encrypt_field(database_url))
            master_db.add(broker)
        else:
            broker.encrypted_db_url = encrypt_field(database_url)
        await master_db.commit()
        await invalidate_tenant_engine(tenant_id)
        return TenantDatabaseResponse(tenant_id=tenant_id, configured=True, migrated=True)
    except HTTPException:
        raise
    except Exception as error:
        await master_db.rollback()
        import logging

        logging.getLogger(__name__).exception("Private database setup failed", exc_info=error)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Private database setup failed") from error
    finally:
        await test_engine.dispose()


@router.post("/database/auto-provision", response_model=TenantDatabaseResponse)
async def auto_provision_private_database(
    claims: dict[str, str] = Depends(require_roles(Role.BROKER_ADMIN, Role.SUPER_ADMIN)),
    master_db: AsyncSession = Depends(get_db),
) -> TenantDatabaseResponse:
    """Provision a DigitalOcean database and complete BYODB onboarding for the tenant."""
    try:
        tenant_id = UUID(claims["tenant_id"])
    except (KeyError, ValueError) as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid tenant identity") from error

    broker = await master_db.get(BrokerTenant, tenant_id)
    if not broker or not broker.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found or inactive")

    try:
        database_url = validate_database_url(await create_digitalocean_postgres(broker.subdomain))
        test_engine = create_async_engine(database_url, pool_pre_ping=True, pool_size=1, max_overflow=0)
        try:
            async with test_engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
            await migrate_tenant_database(database_url)
            broker.encrypted_db_url = encrypt_field(database_url)
            await master_db.commit()
            await invalidate_tenant_engine(tenant_id)
            return TenantDatabaseResponse(tenant_id=tenant_id, configured=True, migrated=True)
        finally:
            await test_engine.dispose()
    except HTTPException:
        raise
    except Exception as error:
        await master_db.rollback()
        import logging

        logging.getLogger(__name__).exception("Automatic private database setup failed", exc_info=error)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Automatic database setup failed") from error
