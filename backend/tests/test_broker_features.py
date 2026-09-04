from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.core.feature_registry import feature_grant_is_active
from app.models import TenantFeatureGrant


def test_only_active_feature_grants_are_visible() -> None:
    now = datetime.now(UTC)
    active = TenantFeatureGrant(
        tenant_id=uuid4(),
        feature_id=uuid4(),
        granted_by=uuid4(),
        status="ENABLED",
        starts_at=now - timedelta(minutes=1),
        ends_at=now + timedelta(minutes=1),
    )
    expired = TenantFeatureGrant(
        tenant_id=active.tenant_id,
        feature_id=uuid4(),
        granted_by=uuid4(),
        status="ENABLED",
        ends_at=now - timedelta(seconds=1),
    )
    disabled = TenantFeatureGrant(
        tenant_id=active.tenant_id,
        feature_id=uuid4(),
        granted_by=uuid4(),
        status="DISABLED",
    )
    assert feature_grant_is_active(active, now) is True
    assert feature_grant_is_active(expired, now) is False
    assert feature_grant_is_active(disabled, now) is False
