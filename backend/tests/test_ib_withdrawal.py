import os
from uuid import uuid4

os.environ.setdefault("JWT_SECRET", "test-jwt-secret")
os.environ.setdefault("FIELD_ENCRYPTION_KEY", "test-field-encryption-key")
os.environ.setdefault("WEBHOOK_SIGNING_SECRET", "test-webhook-secret")

from app.api.v1.trader.ib import _ib_withdrawal_reference


def test_ib_withdrawal_references_are_unique_before_flush() -> None:
    first_id = uuid4()
    second_id = uuid4()

    first_reference = _ib_withdrawal_reference(first_id)
    second_reference = _ib_withdrawal_reference(second_id)

    assert first_reference == f"ib-withdrawal:{first_id}"
    assert second_reference == f"ib-withdrawal:{second_id}"
    assert first_reference != second_reference
