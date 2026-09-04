import os

os.environ.setdefault("JWT_SECRET", "test-jwt-secret")
os.environ.setdefault("FIELD_ENCRYPTION_KEY", "test-field-encryption-key")
os.environ.setdefault("WEBHOOK_SIGNING_SECRET", "test-webhook-secret")

from app.api.v1.broker.finance import TransactionRequest


def test_finance_request_key_is_stable_for_replays() -> None:
    first = TransactionRequest(
        type="DEPOSIT",
        amount="25",
        currency="USD",
        idempotency_key="stable-deposit-key",
    )
    replay = TransactionRequest(
        type="DEPOSIT",
        amount="25",
        currency="USD",
        idempotency_key=first.idempotency_key,
    )

    assert replay.idempotency_key == first.idempotency_key
