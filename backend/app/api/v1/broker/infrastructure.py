"""Independent tenant database and storage configuration APIs."""

import json
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ....core.db_router import get_tenant_db
from ....core.entitlements import (
    EntitlementKind,
    get_infrastructure_entitlement,
)
from ....core.provider_connectors import test_provider_connection
from ....crypto import decrypt_field, encrypt_field
from ....middleware.audit_logger import AuditLogger
from ....models import InfrastructureConfig, IntegrationStatus, Role, Tenant
from ....security import require_roles

router = APIRouter(prefix="/api/v1/broker/infrastructure", tags=["Infrastructure"])
BrokerClaims = Annotated[
    dict[str, str], Depends(require_roles(Role.SUPER_ADMIN, Role.BROKER_ADMIN))
]
InfrastructureKind = Literal["DATABASE", "STORAGE"]
InfrastructureMode = Literal["SAAS", "EXTERNAL"]


class InfrastructurePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: InfrastructureMode
    provider: str | None = Field(default=None, max_length=80)
    engine: str | None = Field(default=None, max_length=40)
    config_json: dict = Field(default_factory=dict)
    credentials: dict | None = None


class InfrastructureResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    kind: InfrastructureKind
    mode: InfrastructureMode
    provider: str | None
    engine: str | None
    config_json: dict
    status: str
    active: bool
    last_error: str | None
    last_verified_at: str | None
    masked_credentials: dict | None


PROVIDERS = {
    "DATABASE": [
        {"id": "SAAS", "name": "SaaS Database", "mode": "SAAS", "supported": True},
        {
            "id": "POSTGRES",
            "name": "PostgreSQL",
            "mode": "EXTERNAL",
            "engine": "POSTGRES",
            "supported": True,
        },
    ],
    "STORAGE": [
        {"id": "SAAS", "name": "SaaS Storage", "mode": "SAAS", "supported": True},
    ],
}
SECRET_KEYS = {
    "password",
    "secret",
    "secret_key",
    "api_key",
    "api_secret",
    "access_token",
    "client_secret",
}


def _safe_config(config: dict) -> dict:
    return {
        key: value for key, value in config.items() if key.lower() not in SECRET_KEYS
    }


def _response(row: InfrastructureConfig | None) -> InfrastructureResponse | None:
    if not row:
        return None
    masked = None
    if row.encrypted_credentials:
        try:
            values = json.loads(decrypt_field(row.encrypted_credentials))
            masked = {
                key: "configured"
                if not isinstance(value, str)
                else f"********{value[-4:]}"
                for key, value in values.items()
            }
        except (ValueError, TypeError, json.JSONDecodeError):
            masked = {"value": "configured"}
    return InfrastructureResponse(
        id=row.id,
        tenant_id=row.tenant_id,
        kind=row.kind,
        mode=row.mode,
        provider=row.provider,
        engine=row.engine,
        config_json=_safe_config(row.config_json or {}),
        status=row.status.value if hasattr(row.status, "value") else row.status,
        active=row.active,
        last_error=row.last_error,
        last_verified_at=row.last_verified_at.isoformat()
        if row.last_verified_at
        else None,
        masked_credentials=masked,
    )


@router.get("/providers")
async def list_providers(
    kind: InfrastructureKind | None = None,
) -> dict[str, list[dict]] | list[dict]:
    return PROVIDERS[kind] if kind else PROVIDERS


@router.get("/{kind}", response_model=InfrastructureResponse | None)
async def get_infrastructure(
    kind: InfrastructureKind,
    claims: BrokerClaims,
    db: AsyncSession = Depends(get_tenant_db),
) -> InfrastructureResponse | None:
    row = await db.scalar(
        select(InfrastructureConfig).where(
            InfrastructureConfig.tenant_id == UUID(claims["tenant_id"]),
            InfrastructureConfig.kind == kind,
        )
    )
    return _response(row)


@router.put("/{kind}", response_model=InfrastructureResponse)
async def configure_infrastructure(
    kind: InfrastructureKind,
    payload: InfrastructurePayload,
    claims: BrokerClaims,
    db: AsyncSession = Depends(get_tenant_db),
) -> InfrastructureResponse:
    tenant_id, actor_id = UUID(claims["tenant_id"]), UUID(claims["sub"])
    tenant = await db.scalar(select(Tenant).where(Tenant.id == tenant_id))
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    entitlement = get_infrastructure_entitlement(tenant.plan, kind, payload.mode)
    if not entitlement.allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"{payload.mode} {kind.lower()} is not allowed on the current plan",
        )
    if payload.mode == "SAAS":
        if payload.credentials:
            raise HTTPException(
                status_code=400,
                detail="SaaS-managed infrastructure does not accept broker credentials",
            )
        result_status, error, encrypted = IntegrationStatus.CONNECTED, None, None
    else:
        if not payload.provider or not payload.credentials:
            raise HTTPException(
                status_code=400,
                detail="External infrastructure requires a provider and credentials",
            )
        if kind == "DATABASE" and payload.provider.upper() not in {
            "POSTGRES",
            "POSTGRESQL",
        }:
            raise HTTPException(
                status_code=422,
                detail="No validated connector is available for this database provider",
            )
        encrypted = encrypt_field(json.dumps(payload.credentials))
        result = await test_provider_connection(
            payload.provider,
            "DATABASE" if kind == "DATABASE" else "EXTERNAL",
            payload.config_json,
            encrypted,
            decrypt_field,
        )
        if result.status != IntegrationStatus.CONNECTED:
            raise HTTPException(
                status_code=422,
                detail={"status": result.status.value, "message": result.message},
            )
        result_status, error = result.status, None
    row = await db.scalar(
        select(InfrastructureConfig)
        .where(
            InfrastructureConfig.tenant_id == tenant_id,
            InfrastructureConfig.kind == kind,
        )
        .with_for_update()
    )
    if not row:
        row = InfrastructureConfig(
            tenant_id=tenant_id,
            kind=kind,
            mode=payload.mode,
            provider=payload.provider,
            engine=payload.engine,
            config_json=payload.config_json,
            encrypted_credentials=encrypted,
            status=result_status.value,
            active=False,
            last_error=error,
            last_verified_at=func.now()
            if result_status == IntegrationStatus.CONNECTED
            else None,
        )
        db.add(row)
    else:
        row.mode, row.provider, row.engine = (
            payload.mode,
            payload.provider,
            payload.engine,
        )
        row.config_json, row.encrypted_credentials = payload.config_json, encrypted
        row.status, row.last_error = result_status.value, error
        row.last_verified_at = (
            func.now() if result_status == IntegrationStatus.CONNECTED else None
        )
        row.active = False
    await AuditLogger.log_update(
        db,
        tenant_id,
        actor_id,
        "INFRASTRUCTURE",
        row.id,
        {
            "action": "CONFIGURED",
            "kind": kind,
            "mode": payload.mode,
            "provider": payload.provider,
            "status": result_status.value,
        },
    )
    await db.commit()
    await db.refresh(row)
    return _response(row)


@router.post("/{kind}/activate", response_model=InfrastructureResponse)
async def activate_infrastructure(
    kind: InfrastructureKind,
    claims: BrokerClaims,
    db: AsyncSession = Depends(get_tenant_db),
    confirm: bool = False,
) -> InfrastructureResponse:
    tenant_id, actor_id = UUID(claims["tenant_id"]), UUID(claims["sub"])
    tenant = await db.scalar(select(Tenant).where(Tenant.id == tenant_id))
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    row = await db.scalar(
        select(InfrastructureConfig)
        .where(
            InfrastructureConfig.tenant_id == tenant_id,
            InfrastructureConfig.kind == kind,
        )
        .with_for_update()
    )
    if not row:
        raise HTTPException(
            status_code=404, detail="Infrastructure configuration not found"
        )
    entitlement = get_infrastructure_entitlement(tenant.plan, kind, row.mode)
    if not entitlement.allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"{row.mode} {kind.lower()} is not allowed on the current plan",
        )
    if (
        row.status != IntegrationStatus.CONNECTED.value
        and row.status != IntegrationStatus.CONNECTED
    ):
        raise HTTPException(
            status_code=409,
            detail="Infrastructure must pass a connection test before activation",
        )
    if row.active and not confirm:
        raise HTTPException(status_code=409, detail="Activation confirmation required")
    row.active = True
    await AuditLogger.log_update(
        db,
        tenant_id,
        actor_id,
        "INFRASTRUCTURE",
        row.id,
        {"action": "ACTIVATE", "kind": kind},
    )
    await db.commit()
    await db.refresh(row)
    return _response(row)
