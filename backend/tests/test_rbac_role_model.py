from uuid import uuid4

from app.models import DynamicRole


def test_dynamic_role_model_exposes_default_role_flag() -> None:
    assert hasattr(DynamicRole, "is_default")

    role = DynamicRole(
        tenant_id=uuid4(),
        name="Sales Manager",
        description="Team lead access",
        is_default=True,
    )

    assert role.is_default is True
