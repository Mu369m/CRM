"""Authenticated AES-256-GCM encryption for broker credentials and PII."""

import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .config import get_settings


def _key() -> bytes:
    """Decode a 32-byte URL-safe base64 key supplied by the secret manager."""
    raw = base64.urlsafe_b64decode(get_settings().field_encryption_key.get_secret_value())
    if len(raw) != 32:
        raise ValueError("FIELD_ENCRYPTION_KEY must decode to exactly 32 bytes")
    return raw


def encrypt_field(value: str) -> str:
    """Encrypt a value with a fresh nonce; output is nonce:ciphertext in base64."""
    nonce = os.urandom(12)
    ciphertext = AESGCM(_key()).encrypt(nonce, value.encode("utf-8"), None)
    return base64.urlsafe_b64encode(nonce + ciphertext).decode("ascii")


def decrypt_field(token: str) -> str:
    """Authenticate and decrypt a field, raising on tampering or invalid key material."""
    packed = base64.urlsafe_b64decode(token.encode("ascii"))
    return AESGCM(_key()).decrypt(packed[:12], packed[12:], None).decode("utf-8")