"""Tenant-safe feature registry and grant decisions."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import FeatureDefinition, Tenant, TenantFeatureGrant


def feature_grant_is_active(
    grant: TenantFeatureGrant, now: datetime | None = None
) -> bool:
    current = now or datetime.now(UTC)
    return (
        grant.status in {"ENABLED", "TRIAL"}
        and (grant.starts_at is None or grant.starts_at <= current)
        and (grant.ends_at is None or grant.ends_at > current)
    )


async def is_feature_enabled(
    db: AsyncSession, tenant_id: UUID, feature_key: str
) -> bool:
    """Return true only when availability, plan eligibility, and grant pass."""
    row = await db.execute(
        select(FeatureDefinition, TenantFeatureGrant, Tenant.plan)
        .join(
            TenantFeatureGrant,
            TenantFeatureGrant.feature_id == FeatureDefinition.id,
        )
        .join(Tenant, Tenant.id == TenantFeatureGrant.tenant_id)
        .where(
            TenantFeatureGrant.tenant_id == tenant_id,
            FeatureDefinition.feature_key == feature_key,
        )
    )
    result = row.first()
    if not result:
        return False
    definition, grant, plan = result
    eligible_plans = definition.eligible_plans or []
    return (
        definition.is_available
        and (not eligible_plans or plan in eligible_plans)
        and feature_grant_is_active(grant)
    )
