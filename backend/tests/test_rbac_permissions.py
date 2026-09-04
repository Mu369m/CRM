import os
from app.middleware.permission_check import STANDARD_PERMISSIONS
from decimal import Decimal

os.environ.setdefault("JWT_SECRET", "test-jwt-secret")
os.environ.setdefault("FIELD_ENCRYPTION_KEY", "test-field-encryption-key")
os.environ.setdefault("WEBHOOK_SIGNING_SECRET", "test-webhook-secret")

from app.api.v1.broker.withdrawals import _available_client_balance
from app.core.seed_data import SeedDataInitializer
from app.models import Client


def test_seeded_permissions_match_enforced_permission_catalog() -> None:
    seeded_codes = set(SeedDataInitializer.STANDARD_PERMISSIONS)

    assert seeded_codes == set(STANDARD_PERMISSIONS)
    assert {"kyc.upload", "kyc.reject"}.issubset(seeded_codes)
    assert {
        "workflows.view",
        "workflows.create",
        "workflows.edit",
        "workflows.delete",
    }.issubset(seeded_codes)


def test_system_seed_roles_are_marked_as_default() -> None:
    assert all(
        role_config.get("is_default", True)
        for role_config in SeedDataInitializer.DEFAULT_ROLES.values()
    )


def test_uninitialized_client_balance_is_zero() -> None:
    client = Client(net_deposits=None)

    assert _available_client_balance(client) == Decimal("0")
