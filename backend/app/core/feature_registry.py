"""Tenant-safe feature registry and grant decisions."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import FeatureDefinition, Tenant, TenantFeatureGrant


def feature_relationships_are_satisfied(
    dependency_keys: list[str] | None,
    conflict_keys: list[str] | None,
    active_keys: set[str],
) -> bool:
    dependencies = set(dependency_keys or [])
    conflicts = set(conflict_keys or [])
    return dependencies.issubset(active_keys) and not conflicts.intersection(
        active_keys
    )


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
    base_enabled = (
        definition.is_available
        and (not eligible_plans or plan in eligible_plans)
        and feature_grant_is_active(grant)
    )
    if not base_enabled:
        return False

    related_keys = set(definition.dependency_keys or []) | set(
        definition.conflict_keys or []
    )
    if not related_keys:
        return True
    related_rows = await db.execute(
        select(FeatureDefinition, TenantFeatureGrant)
        .join(TenantFeatureGrant, TenantFeatureGrant.feature_id == FeatureDefinition.id)
        .where(
            TenantFeatureGrant.tenant_id == tenant_id,
            FeatureDefinition.feature_key.in_(related_keys),
        )
    )
    active_keys = {
        related_definition.feature_key
        for related_definition, related_grant in related_rows.all()
        if feature_grant_is_active(related_grant)
    }
    return feature_relationships_are_satisfied(
        definition.dependency_keys, definition.conflict_keys, active_keys
    )
