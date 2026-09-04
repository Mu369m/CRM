"""Owner controls for reusable feature definitions and tenant grants."""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ....db import get_db
from ....middleware.audit_logger import AuditLogger
from ....models import FeatureDefinition, Role, Tenant, TenantFeatureGrant, User
from ....security import get_current_owner_user

router = APIRouter(prefix="/api/v1/owner/features", tags=["Owner Features"])
OwnerClaims = dict[str, str]


async def verified_owner_claims(
    claims: OwnerClaims = Depends(get_current_owner_user),
    db: AsyncSession = Depends(get_db),
) -> OwnerClaims:
    user = await db.scalar(select(User).where(User.id == UUID(claims["sub"])))
    if not user or user.role != Role.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="Owner permissions required")
    return claims


class FeatureCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    feature_key: str = Field(min_length=2, max_length=120, pattern=r"^[a-z0-9_]+$")
    name: str = Field(min_length=1, max_length=160)
    feature_type: str = Field(default="MODULE", max_length=40)
    version: str = Field(default="1.0", max_length=30)
    eligible_plans: list[str] = Field(default_factory=list)
    pricing_type: str = Field(default="INCLUDED", max_length=30)
    configuration_schema: dict = Field(default_factory=dict)
    internal_notes: str | None = Field(default=None, max_length=2000)


class FeatureResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    feature_key: str
    name: str
    feature_type: str
    version: str
    is_available: bool
    eligible_plans: list
    pricing_type: str
    configuration_schema: dict
    internal_notes: str | None


class GrantRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_id: UUID
    status: str = Field(pattern=r"^(ENABLED|DISABLED|TRIAL|SCHEDULED|SUSPENDED)$")
    configuration: dict = Field(default_factory=dict)
    starts_at: datetime | None = None
    ends_at: datetime | None = None


class GrantResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    tenant_id: UUID
    feature_id: UUID
    status: str
    configuration: dict
    starts_at: datetime | None
    ends_at: datetime | None
    granted_by: UUID


def _validate_configuration(feature: FeatureDefinition, configuration: dict) -> None:
    schema = feature.configuration_schema or {}
    properties = schema.get("properties", {})
    required = set(schema.get("required", []))
    missing = required - set(configuration)
    unknown = set(configuration) - set(properties)
    if missing or (properties and unknown):
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Invalid feature configuration",
                "missing": sorted(missing),
                "unsupported": sorted(unknown),
            },
        )
    type_map = {
        "string": str,
        "number": (int, float),
        "integer": int,
        "boolean": bool,
        "object": dict,
        "array": list,
    }
    for key, definition in properties.items():
        if key in configuration and definition.get("type") in type_map:
            expected = type_map[definition["type"]]
            if not isinstance(configuration[key], expected) or (
                definition["type"] in {"number", "integer"}
                and isinstance(configuration[key], bool)
            ):
                raise HTTPException(
                    status_code=422,
                    detail=f"Invalid type for feature configuration key: {key}",
                )


@router.get("", response_model=list[FeatureResponse])
async def list_features(
    db: AsyncSession = Depends(get_db),
    _: OwnerClaims = Depends(verified_owner_claims),
) -> list[FeatureDefinition]:
    return list(
        await db.scalars(
            select(FeatureDefinition).order_by(FeatureDefinition.feature_key)
        )
    )


@router.post("", response_model=FeatureResponse, status_code=status.HTTP_201_CREATED)
async def create_feature(
    payload: FeatureCreate,
    claims: OwnerClaims = Depends(verified_owner_claims),
    db: AsyncSession = Depends(get_db),
) -> FeatureDefinition:
    existing = await db.scalar(
        select(FeatureDefinition).where(
            FeatureDefinition.feature_key == payload.feature_key
        )
    )
    if existing:
        raise HTTPException(status_code=409, detail="Feature key already exists")
    feature = FeatureDefinition(**payload.model_dump())
    db.add(feature)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Feature key already exists")
    await AuditLogger.log_create(
        db,
        UUID(claims["tenant_id"]),
        UUID(claims["sub"]),
        "FEATURE_DEFINITION",
        feature.id,
        {
            "feature_key": feature.feature_key,
            "name": feature.name,
            "feature_type": feature.feature_type,
            "version": feature.version,
            "eligible_plans": feature.eligible_plans,
            "pricing_type": feature.pricing_type,
            "configuration_schema": feature.configuration_schema,
            "internal_notes": feature.internal_notes,
        },
    )
    await db.commit()
    await db.refresh(feature)
    return feature


@router.post("/{feature_id}/grants", response_model=GrantResponse)
async def grant_feature(
    feature_id: UUID,
    payload: GrantRequest,
    claims: OwnerClaims = Depends(verified_owner_claims),
    db: AsyncSession = Depends(get_db),
) -> TenantFeatureGrant:
    feature = await db.get(FeatureDefinition, feature_id)
    tenant = await db.get(Tenant, payload.tenant_id)
    if not feature or not tenant:
        raise HTTPException(status_code=404, detail="Feature or tenant not found")
    if payload.ends_at and payload.starts_at and payload.ends_at <= payload.starts_at:
        raise HTTPException(status_code=422, detail="Grant end must be after its start")
    _validate_configuration(feature, payload.configuration)
    grant = await db.scalar(
        select(TenantFeatureGrant)
        .where(
            TenantFeatureGrant.feature_id == feature_id,
            TenantFeatureGrant.tenant_id == payload.tenant_id,
        )
        .with_for_update()
    )
    changes = payload.model_dump()
    changes.pop("tenant_id")
    old_values = None
    if grant:
        old_values = {
            "status": grant.status,
            "configuration": grant.configuration,
            "starts_at": grant.starts_at.isoformat() if grant.starts_at else None,
            "ends_at": grant.ends_at.isoformat() if grant.ends_at else None,
        }
        for key, value in changes.items():
            setattr(grant, key, value)
        action = "UPDATED"
    else:
        grant = TenantFeatureGrant(
            feature_id=feature_id,
            tenant_id=payload.tenant_id,
            granted_by=UUID(claims["sub"]),
            **changes,
        )
        db.add(grant)
        action = "GRANTED"
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        feature = await db.get(FeatureDefinition, feature_id)
        grant = await db.scalar(
            select(TenantFeatureGrant)
            .where(
                TenantFeatureGrant.feature_id == feature_id,
                TenantFeatureGrant.tenant_id == payload.tenant_id,
            )
            .with_for_update()
        )
        if not grant:
            raise HTTPException(status_code=409, detail="Feature grant conflict")
        old_values = {
            "status": grant.status,
            "configuration": grant.configuration,
            "starts_at": grant.starts_at.isoformat() if grant.starts_at else None,
            "ends_at": grant.ends_at.isoformat() if grant.ends_at else None,
        }
        for key, value in changes.items():
            setattr(grant, key, value)
        action = "UPDATED"
        await db.flush()
    audit_payload = {
        "feature_key": feature.feature_key,
        "action": action,
        "status": grant.status,
        "configuration": grant.configuration,
        "starts_at": grant.starts_at.isoformat() if grant.starts_at else None,
        "ends_at": grant.ends_at.isoformat() if grant.ends_at else None,
        "old_values": old_values,
    }
    if action == "GRANTED":
        await AuditLogger.log_create(
            db,
            payload.tenant_id,
            UUID(claims["sub"]),
            "FEATURE_GRANT",
            grant.id,
            audit_payload,
        )
    else:
        await AuditLogger.log_update(
            db,
            payload.tenant_id,
            UUID(claims["sub"]),
            "FEATURE_GRANT",
            grant.id,
            audit_payload,
        )
    await db.commit()
    await db.refresh(grant)
    return grant
