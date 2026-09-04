from app.core.entitlements import (
    EntitlementKind,
    InfrastructureMode,
    get_infrastructure_entitlement,
)


def test_starter_can_use_included_saas_storage_only() -> None:
    decision = get_infrastructure_entitlement(
        "STARTER", EntitlementKind.STORAGE, InfrastructureMode.SAAS
    )
    assert decision.allowed is True
    assert decision.included is True
    assert decision.billable is False
    assert decision.quota_gb == 50

    byo = get_infrastructure_entitlement(
        "STARTER", EntitlementKind.STORAGE, InfrastructureMode.EXTERNAL
    )
    assert byo.allowed is False


def test_enterprise_external_infrastructure_is_allowed_but_not_included() -> None:
    decision = get_infrastructure_entitlement(
        "ENTERPRISE", EntitlementKind.DATABASE, InfrastructureMode.EXTERNAL
    )
    assert decision.allowed is True
    assert decision.included is False
    assert decision.billable is False


def test_unknown_plan_fails_closed() -> None:
    decision = get_infrastructure_entitlement(
        "UNKNOWN", EntitlementKind.DATABASE, InfrastructureMode.SAAS
    )
    assert decision.allowed is False