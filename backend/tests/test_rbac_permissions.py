from app.core.seed_data import SeedDataInitializer
from app.middleware.permission_check import STANDARD_PERMISSIONS


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
