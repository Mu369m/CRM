from app.core.integration_architecture import (
    BrokerIntegrationCheck,
    can_use_integration,
    mask_secret,
)


def test_mask_secret_hides_value() -> None:
    masked = mask_secret("sk_live_1234567890")
    assert masked.startswith("••")
    assert "1234567890" in masked
    assert "sk_live" not in masked


def test_can_use_integration_requires_every_scope() -> None:
    result = can_use_integration(
        global_available=True,
        broker_plan_allows=True,
        broker_enabled=True,
        user_permission=True,
    )
    assert result is True

    result = can_use_integration(
        global_available=False,
        broker_plan_allows=True,
        broker_enabled=True,
        user_permission=True,
    )
    assert result is False

    result = can_use_integration(
        global_available=True,
        broker_plan_allows=False,
        broker_enabled=True,
        user_permission=True,
    )
    assert result is False


def test_can_use_integration_accepts_check_object() -> None:
    check = BrokerIntegrationCheck(
        global_available=True,
        broker_plan_allows=True,
        broker_enabled=True,
        user_permission=True,
    )
    assert can_use_integration(check) is True
