from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.core.feature_registry import feature_grant_is_active
from app.models import TenantFeatureGrant


def test_enabled_grant_is_active_within_window() -> None:
    now = datetime.now(UTC)
    grant = TenantFeatureGrant(
        tenant_id=uuid4(),
        feature_id=uuid4(),
        granted_by=uuid4(),
        status="ENABLED",
        starts_at=now - timedelta(minutes=1),
        ends_at=now + timedelta(minutes=1),
    )
    assert feature_grant_is_active(grant, now) is True


def test_expired_or_disabled_grant_is_inactive() -> None:
    now = datetime.now(UTC)
    expired = TenantFeatureGrant(
        tenant_id=uuid4(),
        feature_id=uuid4(),
        granted_by=uuid4(),
        status="ENABLED",
        ends_at=now - timedelta(seconds=1),
    )
    disabled = TenantFeatureGrant(
        tenant_id=uuid4(),
        feature_id=uuid4(),
        granted_by=uuid4(),
        status="DISABLED",
    )
    assert feature_grant_is_active(expired, now) is False
    assert feature_grant_is_active(disabled, now) is False


def test_trial_grant_is_active_without_schedule() -> None:
    grant = TenantFeatureGrant(
        tenant_id=uuid4(),
        feature_id=uuid4(),
        granted_by=uuid4(),
        status="TRIAL",
    )
    assert feature_grant_is_active(grant) is True
