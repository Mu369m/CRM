"""Tenant-scoped feature visibility for Broker Admin users."""

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ....core.db_router import get_tenant_db
from ....core.feature_registry import feature_grant_is_active
from ....models import FeatureDefinition, Role, TenantFeatureGrant
from ....security import require_roles

router = APIRouter(prefix="/api/v1/broker/features", tags=["Broker Features"])
BrokerClaims = dict[str, str]


class BrokerFeatureResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    feature_key: str
    name: str
    feature_type: str
    version: str
    status: str
    configuration: dict
    starts_at: datetime | None
    ends_at: datetime | None


@router.get("", response_model=list[BrokerFeatureResponse])
async def list_effective_features(
    claims: BrokerClaims = Depends(
        require_roles(
            Role.SUPER_ADMIN,
            Role.BROKER_ADMIN,
            Role.COMPLIANCE,
            Role.FINANCE,
            Role.SALES,
        )
    ),
    db: AsyncSession = Depends(get_tenant_db),
) -> list[BrokerFeatureResponse]:
    tenant_id = UUID(claims["tenant_id"])
    rows = await db.execute(
        select(FeatureDefinition, TenantFeatureGrant)
        .join(
            TenantFeatureGrant,
            TenantFeatureGrant.feature_id == FeatureDefinition.id,
        )
        .where(
            TenantFeatureGrant.tenant_id == tenant_id,
            FeatureDefinition.is_available.is_(True),
        )
        .order_by(FeatureDefinition.feature_key)
    )
    now = datetime.now(UTC)
    return [
        BrokerFeatureResponse(
            feature_key=definition.feature_key,
            name=definition.name,
            feature_type=definition.feature_type,
            version=definition.version,
            status=grant.status,
            configuration=grant.configuration or {},
            starts_at=grant.starts_at,
            ends_at=grant.ends_at,
        )
        for definition, grant in rows.all()
        if feature_grant_is_active(grant, now)
    ]
