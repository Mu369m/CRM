"""Broker-owned dynamic settings endpoints."""

from enum import StrEnum
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ....db import get_db
from ....models import Role, TenantSettings
from ....security import require_roles

router = APIRouter(prefix="/api/v1/broker/settings", tags=["Broker Settings"])


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
    claims: Annotated[dict[str, str], Depends(require_roles(Role.SUPER_ADMIN, Role.BROKER_ADMIN, Role.COMPLIANCE))],
    db: AsyncSession = Depends(get_db),
) -> KycSchemaPayload:
    settings = await db.get(TenantSettings, UUID(claims["tenant_id"]))
    return KycSchemaPayload.model_validate(settings.kyc_schema if settings and settings.kyc_schema else {})


@router.post("/kyc-schema", response_model=KycSchemaPayload)
async def save_kyc_schema(
    payload: KycSchemaPayload,
    claims: Annotated[dict[str, str], Depends(require_roles(Role.SUPER_ADMIN, Role.BROKER_ADMIN, Role.COMPLIANCE))],
    db: AsyncSession = Depends(get_db),
) -> KycSchemaPayload:
    settings = await db.get(TenantSettings, UUID(claims["tenant_id"]))
    if not settings:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant settings not found")
    settings.kyc_schema = payload.model_dump(mode="json")
    await db.commit()
    return payload