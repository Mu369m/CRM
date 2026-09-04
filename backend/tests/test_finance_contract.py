import os

os.environ.setdefault("JWT_SECRET", "test-jwt-secret")
os.environ.setdefault("FIELD_ENCRYPTION_KEY", "test-field-encryption-key")
os.environ.setdefault("WEBHOOK_SIGNING_SECRET", "test-webhook-secret")

import pytest
from pydantic import ValidationError

from app.api.v1.broker.finance import TransactionRequest


def test_transaction_request_requires_idempotency_key() -> None:
    with pytest.raises(ValidationError):
        TransactionRequest(type="DEPOSIT", amount="10", currency="USD")

    request = TransactionRequest(
        type="DEPOSIT",
        amount="10",
        currency="USD",
        idempotency_key="deposit-request-1234",
    )

    assert request.idempotency_key == "deposit-request-1234"
