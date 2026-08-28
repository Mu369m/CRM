"""Focused tests for cryptographic and webhook security primitives."""

import base64
import hashlib
import hmac
import os


def test_webhook_signature_comparison() -> None:
    body = b'{"event":"deposit.received"}'
    secret = "test-provider-secret"
    signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    assert hmac.compare_digest(signature, signature)
    assert not hmac.compare_digest(signature, "0" * 64)


def test_aes_key_material_is_32_bytes() -> None:
    key = base64.urlsafe_b64encode(os.urandom(32))
    assert len(base64.urlsafe_b64decode(key)) == 32
