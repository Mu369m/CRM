"""Broker-owned dynamic settings endpoints."""

from enum import StrEnum
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ....core.db_router import get_tenant_db
from ....models import Role, TenantSettings, TenantThemeVersion
from ....security import require_roles
from ....middleware.audit_logger import AuditLogger
from ....branding_schemas import (
    ThemeDraftPayload,
    ThemeDraftResponse,
    ThemeVersionResponse,
)
from sqlalchemy import func, select

router = APIRouter(prefix="/api/v1/broker/settings", tags=["Broker Settings"])

THEME_ROLES = (Role.SUPER_ADMIN, Role.BROKER_ADMIN)


def _theme_response(theme: TenantThemeVersion | None) -> ThemeVersionResponse | None:
    if not theme:
        return None
    return ThemeVersionResponse(
        id=str(theme.id),
        version=theme.version,
        status=theme.status,
        config=theme.config,
        created_at=theme.created_at.isoformat(),
        published_at=theme.published_at.isoformat() if theme.published_at else None,
    )


@router.get("/theme", response_model=ThemeDraftResponse)
async def get_theme(
    claims: Annotated[dict[str, str], Depends(require_roles(*THEME_ROLES))],
    db: AsyncSession = Depends(get_tenant_db),
) -> ThemeDraftResponse:
    tenant_id = UUID(claims["tenant_id"])
    versions = (
        await db.scalars(
            select(TenantThemeVersion)
            .where(TenantThemeVersion.tenant_id == tenant_id)
            .order_by(TenantThemeVersion.version.desc())
        )
    ).all()
    return ThemeDraftResponse(
        draft=_theme_response(
            next((item for item in versions if item.status == "DRAFT"), None)
        ),
        published=_theme_response(
            next((item for item in versions if item.status == "PUBLISHED"), None)
        ),
    )


@router.put("/theme/draft", response_model=ThemeVersionResponse)
async def save_theme_draft(
    payload: ThemeDraftPayload,
    claims: Annotated[dict[str, str], Depends(require_roles(*THEME_ROLES))],
    db: AsyncSession = Depends(get_tenant_db),
) -> ThemeVersionResponse:
    tenant_id, actor_id = UUID(claims["tenant_id"]), UUID(claims["sub"])
    draft = await db.scalar(
        select(TenantThemeVersion)
        .where(
            TenantThemeVersion.tenant_id == tenant_id,
            TenantThemeVersion.status == "DRAFT",
        )
        .order_by(TenantThemeVersion.version.desc())
    )
    if draft:
        draft.config = payload.config.model_dump(mode="json")
    else:
        latest = await db.scalar(
            select(func.max(TenantThemeVersion.version)).where(
                TenantThemeVersion.tenant_id == tenant_id
            )
        )
        draft = TenantThemeVersion(
            tenant_id=tenant_id,
            version=(latest or 0) + 1,
            status="DRAFT",
            config=payload.config.model_dump(mode="json"),
            created_by=actor_id,
        )
        db.add(draft)
    await AuditLogger.log_update(
        db, tenant_id, actor_id, "TENANT_THEME", draft.id, {"status": "DRAFT"}
    )
    await db.commit()
    await db.refresh(draft)
    return _theme_response(draft)


@router.post("/theme/publish", response_model=ThemeVersionResponse)
async def publish_theme(
    claims: Annotated[dict[str, str], Depends(require_roles(*THEME_ROLES))],
    db: AsyncSession = Depends(get_tenant_db),
) -> ThemeVersionResponse:
    tenant_id, actor_id = UUID(claims["tenant_id"]), UUID(claims["sub"])
    draft = await db.scalar(
        select(TenantThemeVersion)
        .where(
            TenantThemeVersion.tenant_id == tenant_id,
            TenantThemeVersion.status == "DRAFT",
        )
        .order_by(TenantThemeVersion.version.desc())
        .with_for_update()
    )
    if not draft:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Theme draft not found"
        )
    await db.execute(
        TenantThemeVersion.__table__.update()
        .where(
            TenantThemeVersion.tenant_id == tenant_id,
            TenantThemeVersion.status == "PUBLISHED",
        )
        .values(status="ARCHIVED")
    )
    draft.status, draft.published_at = "PUBLISHED", func.now()
    await AuditLogger.log_update(
        db, tenant_id, actor_id, "TENANT_THEME", draft.id, {"status": "PUBLISHED"}
    )
    await db.commit()
    await db.refresh(draft)
    return _theme_response(draft)


class KycFieldState(StrEnum):
    DISABLED = "DISABLED"
    OPTIONAL = "OPTIONAL"
    MANDATORY = "MANDATORY"


class KycCustomField(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str = Field(pattern=r"^[a-z0-9_]+$", min_length=1, max_length=80)
    label: str = Field(min_length=1, max_length=120)
    type: str = Field(pattern=r"^(text|select|checkbox)$")
    required: bool = False


class KycSchemaPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fields: dict[str, KycFieldState] = Field(default_factory=dict, max_length=200)
    custom_fields: list[KycCustomField] = Field(default_factory=list, max_length=100)


@router.get("/kyc-schema", response_model=KycSchemaPayload)
async def get_kyc_schema(
    claims: Annotated[
        dict[str, str],
        Depends(require_roles(Role.SUPER_ADMIN, Role.BROKER_ADMIN, Role.COMPLIANCE)),
    ],
    db: AsyncSession = Depends(get_tenant_db),
) -> KycSchemaPayload:
    settings = await db.get(TenantSettings, UUID(claims["tenant_id"]))
    return KycSchemaPayload.model_validate(
        settings.kyc_schema if settings and settings.kyc_schema else {}
    )


@router.post("/kyc-schema", response_model=KycSchemaPayload)
async def save_kyc_schema(
    payload: KycSchemaPayload,
    claims: Annotated[
        dict[str, str],
        Depends(require_roles(Role.SUPER_ADMIN, Role.BROKER_ADMIN, Role.COMPLIANCE)),
    ],
    db: AsyncSession = Depends(get_tenant_db),
) -> KycSchemaPayload:
    settings = await db.get(TenantSettings, UUID(claims["tenant_id"]))
    if not settings:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Tenant settings not found"
        )
    settings.kyc_schema = payload.model_dump(mode="json")
    await db.commit()
    return payload
