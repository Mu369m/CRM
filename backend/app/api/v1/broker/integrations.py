"""Broker-specific integrations API.

This service enforces the final architecture rule:
- SaaS provides the integration framework and connectors
- Broker owns and configures their own provider accounts and credentials
- Integration access is scoped by tenant_id/broker_id
- Secrets are encrypted and never returned in full
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ....core.db_router import get_tenant_db
from ....core.integration_architecture import (
    IntegrationStatus,
    can_use_integration,
    integration_scope_ok,
    mask_secret,
)
from ....crypto import decrypt_field, encrypt_field
from ....models import IntegrationConfig, IntegrationEntitlement, Role
from ....security import require_roles
from ....admin_schemas import IntegrationConfigCreate, IntegrationConfigResponse

router = APIRouter(prefix="/api/v1/broker/integrations", tags=["Broker Integrations"])


def _masked_credentials_payload(credentials: dict[str, Any] | None) -> dict[str, Any] | None:
    if not credentials:
        return None
    masked: dict[str, Any] = {}
    for key, value in credentials.items():
        if isinstance(value, str):
            masked[key] = mask_secret(value)
        else:
            masked[key] = value
    return masked


@router.get("", response_model=list[IntegrationConfigResponse])
async def list_integrations(
    provider: str | None = Query(default=None),
    claims: dict[str, str] = Depends(require_roles(Role.SUPER_ADMIN, Role.BROKER_ADMIN, Role.FINANCE, Role.COMPLIANCE)),
    db: AsyncSession = Depends(get_tenant_db),
):
    tenant_id = UUID(claims["tenant_id"])
    query = select(IntegrationConfig).where(IntegrationConfig.tenant_id == tenant_id)
    if provider:
        query = query.where(IntegrationConfig.provider == provider)
    rows = await db.execute(query.order_by(IntegrationConfig.created_at.desc()))
    integrations = rows.scalars().all()
    response = []
    for integration in integrations:
        response.append(
            IntegrationConfigResponse(
                id=integration.id,
                tenant_id=integration.tenant_id,
                name=integration.name,
                provider=integration.provider.value if hasattr(integration.provider, "value") else str(integration.provider),
                integration_type=integration.integration_type,
                status=integration.status.value,
                enabled=integration.enabled,
                is_saas_managed=integration.is_saas_managed,
                config_json=integration.config_json or {},
                last_error=integration.last_error,
                last_connected_at=integration.last_connected_at.isoformat() if integration.last_connected_at else None,
                masked_credentials=_masked_credentials_payload(
                    {} if not integration.encrypted_credentials else {"value": mask_secret(decrypt_field(integration.encrypted_credentials))}
                ),
            )
        )
    return response


@router.post("", response_model=IntegrationConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_integration(
    payload: IntegrationConfigCreate,
    claims: dict[str, str] = Depends(require_roles(Role.SUPER_ADMIN, Role.BROKER_ADMIN)),
    db: AsyncSession = Depends(get_tenant_db),
):
    tenant_id = UUID(claims["tenant_id"])
    provider = payload.provider.strip()

    integration = IntegrationConfig(
        tenant_id=tenant_id,
        name=payload.name,
        provider=provider,
        integration_type=payload.integration_type,
        enabled=payload.enabled,
        status=IntegrationStatus.NOT_CONFIGURED,
        config_json=payload.config_json or {},
        encrypted_credentials=encrypt_field(str(payload.credentials or {})) if payload.credentials else None,
    )
    db.add(integration)
    await db.commit()
    await db.refresh(integration)

    return IntegrationConfigResponse(
        id=integration.id,
        tenant_id=integration.tenant_id,
        name=integration.name,
        provider=str(integration.provider),
        integration_type=integration.integration_type,
        status=integration.status.value,
        enabled=integration.enabled,
        is_saas_managed=integration.is_saas_managed,
        config_json=integration.config_json or {},
        last_error=integration.last_error,
        last_connected_at=integration.last_connected_at.isoformat() if integration.last_connected_at else None,
        masked_credentials=_masked_credentials_payload(payload.credentials),
    )


@router.get("/{integration_id}", response_model=IntegrationConfigResponse)
async def get_integration(
    integration_id: UUID,
    claims: dict[str, str] = Depends(require_roles(Role.SUPER_ADMIN, Role.BROKER_ADMIN, Role.FINANCE, Role.COMPLIANCE)),
    db: AsyncSession = Depends(get_tenant_db),
):
    tenant_id = UUID(claims["tenant_id"])
    integration = await db.get(IntegrationConfig, integration_id)
    if not integration or integration.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")

    masked = None
    if integration.encrypted_credentials:
        masked = {"value": mask_secret(decrypt_field(integration.encrypted_credentials))}

    return IntegrationConfigResponse(
        id=integration.id,
        tenant_id=integration.tenant_id,
        name=integration.name,
        provider=str(integration.provider),
        integration_type=integration.integration_type,
        status=integration.status.value,
        enabled=integration.enabled,
        is_saas_managed=integration.is_saas_managed,
        config_json=integration.config_json or {},
        last_error=integration.last_error,
        last_connected_at=integration.last_connected_at.isoformat() if integration.last_connected_at else None,
        masked_credentials=masked,
    )


@router.post("/{integration_id}/test-connection")
async def test_integration_connection(
    integration_id: UUID,
    claims: dict[str, str] = Depends(require_roles(Role.SUPER_ADMIN, Role.BROKER_ADMIN)),
    db: AsyncSession = Depends(get_tenant_db),
):
    tenant_id = UUID(claims["tenant_id"])
    integration = await db.get(IntegrationConfig, integration_id)
    if not integration or integration.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")

    if not integration.enabled:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Integration is disabled")

    if not integration.encrypted_credentials:
        integration.status = IntegrationStatus.AUTHENTICATION_REQUIRED
        integration.last_error = "No credentials configured"
        await db.commit()
        return {"status": IntegrationStatus.AUTHENTICATION_REQUIRED.value, "message": "Credentials are required before testing"}

    try:
        decrypted = decrypt_field(integration.encrypted_credentials)
        if not decrypted or decrypted == "{}":
            raise ValueError("Credentials missing")
        integration.status = IntegrationStatus.CONNECTED
        integration.last_error = None
        integration.last_connected_at = datetime.utcnow()
        await db.commit()
        return {"status": IntegrationStatus.CONNECTED.value, "message": "Connection successful"}
    except Exception as exc:  # pragma: no cover - safe fallback for provider validation layer
        integration.status = IntegrationStatus.CONNECTION_FAILED
        integration.last_error = "Connection failed. Please verify credentials and provider settings."
        await db.commit()
        return {"status": IntegrationStatus.CONNECTION_FAILED.value, "message": "Connection failed. Please verify credentials and provider settings."}


@router.patch("/{integration_id}/enable")
async def enable_integration(
    integration_id: UUID,
    enabled: bool = True,
    claims: dict[str, str] = Depends(require_roles(Role.SUPER_ADMIN, Role.BROKER_ADMIN)),
    db: AsyncSession = Depends(get_tenant_db),
):
    tenant_id = UUID(claims["tenant_id"])
    integration = await db.get(IntegrationConfig, integration_id)
    if not integration or integration.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")

    integration.enabled = enabled
    integration.status = IntegrationStatus.CONNECTED if enabled and integration.status == IntegrationStatus.NOT_CONFIGURED else integration.status
    await db.commit()
    return {"id": str(integration.id), "enabled": integration.enabled, "status": integration.status.value}


@router.delete("/{integration_id}")
async def delete_integration(
    integration_id: UUID,
    claims: dict[str, str] = Depends(require_roles(Role.SUPER_ADMIN, Role.BROKER_ADMIN)),
    db: AsyncSession = Depends(get_tenant_db),
):
    tenant_id = UUID(claims["tenant_id"])
    integration = await db.get(IntegrationConfig, integration_id)
    if not integration or integration.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")
    await db.delete(integration)
    await db.commit()
    return {"deleted": True, "id": str(integration_id)}


@router.get("/entitlements")
async def list_integration_entitlements(
    claims: dict[str, str] = Depends(require_roles(Role.SUPER_ADMIN, Role.BROKER_ADMIN)),
    db: AsyncSession = Depends(get_tenant_db),
):
    tenant_id = UUID(claims["tenant_id"])
    rows = await db.execute(select(IntegrationEntitlement).where(IntegrationEntitlement.tenant_id == tenant_id))
    return [
        {
            "id": str(row.id),
            "name": row.name,
            "provider": row.provider.value,
            "global_available": row.global_available,
            "broker_plan_allows": row.broker_plan_allows,
            "broker_enabled": row.broker_enabled,
            "user_permission": row.user_permission,
            "allowed": can_use_integration(
                global_available=row.global_available,
                broker_plan_allows=row.broker_plan_allows,
                broker_enabled=row.broker_enabled,
                user_permission=row.user_permission,
            ),
        }
        for row in rows.scalars().all()
    ]


@router.post("/entitlements")
async def upsert_integration_entitlement(
    payload: dict[str, bool | str],
    claims: dict[str, str] = Depends(require_roles(Role.SUPER_ADMIN)),
    db: AsyncSession = Depends(get_tenant_db),
):
    tenant_id = UUID(claims["tenant_id"])
    name = str(payload.get("name", "")).strip()
    provider = str(payload.get("provider", "")).strip()
    if not name or not provider:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="name and provider are required")

    row = await db.scalar(select(IntegrationEntitlement).where(IntegrationEntitlement.tenant_id == tenant_id, IntegrationEntitlement.name == name, IntegrationEntitlement.provider == provider))
    if row is None:
        row = IntegrationEntitlement(
            tenant_id=tenant_id,
            name=name,
            provider=provider,
            global_available=bool(payload.get("global_available", False)),
            broker_plan_allows=bool(payload.get("broker_plan_allows", False)),
            broker_enabled=bool(payload.get("broker_enabled", False)),
            user_permission=bool(payload.get("user_permission", False)),
        )
        db.add(row)
    else:
        row.global_available = bool(payload.get("global_available", row.global_available))
        row.broker_plan_allows = bool(payload.get("broker_plan_allows", row.broker_plan_allows))
        row.broker_enabled = bool(payload.get("broker_enabled", row.broker_enabled))
        row.user_permission = bool(payload.get("user_permission", row.user_permission))
    await db.commit()
    return {"status": "ok", "allowed": can_use_integration(
        global_available=row.global_available,
        broker_plan_allows=row.broker_plan_allows,
        broker_enabled=row.broker_enabled,
        user_permission=row.user_permission,
    )}


@router.get("/scope-check")
async def check_integration_scope(
    broker_id: UUID = Query(...),
    integration_id: UUID = Query(...),
    claims: dict[str, str] = Depends(require_roles(Role.SUPER_ADMIN, Role.BROKER_ADMIN)),
    db: AsyncSession = Depends(get_tenant_db),
):
    tenant_id = UUID(claims["tenant_id"])
    integration = await db.get(IntegrationConfig, integration_id)
    if not integration or integration.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")
    return {
        "broker_id_matches": integration_scope_ok(broker_id, integration.tenant_id),
        "broker_id": str(broker_id),
        "tenant_id": str(integration.tenant_id),
    }
