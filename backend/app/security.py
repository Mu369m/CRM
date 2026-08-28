"""Password hashing, JWT claims, and role enforcement."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
import pyotp
from argon2 import PasswordHasher
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from .config import get_settings
from .models import Role

_hasher = PasswordHasher()
_oauth2 = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def hash_password(password: str) -> str:
    """Hash passwords with Argon2id; plaintext credentials never reach persistence."""
    return _hasher.hash(password)


def verify_password(password: str, encoded: str) -> bool:
    """Verify a password without exposing whether a user exists to callers."""
    try:
        return _hasher.verify(encoded, password)
    except Exception:
        return False


def new_totp_secret() -> str:
    """Create a per-user secret; persist it encrypted and never log it."""
    return pyotp.random_base32()


def verify_totp(secret: str, code: str) -> bool:
    """Accept only the current time window, with format validation delegated to pyotp."""
    return pyotp.TOTP(secret).verify(code, valid_window=1)


def create_access_token(user_id: UUID, tenant_id: UUID, role: Role) -> str:
    """Issue a short-lived token containing only authorization identifiers."""
    settings = get_settings()
    expires = datetime.now(UTC) + timedelta(minutes=settings.access_token_minutes)
    return jwt.encode(
        {"sub": str(user_id), "tenant_id": str(tenant_id), "role": role.value, "exp": expires},
        settings.jwt_secret.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )


def current_claims(token: str = Depends(_oauth2)) -> dict[str, str]:
    """Decode and validate issuer-independent access claims."""
    settings = get_settings()
    try:
        claims = jwt.decode(token, settings.jwt_secret.get_secret_value(), algorithms=[settings.jwt_algorithm])
        if not all(claims.get(key) for key in ("sub", "tenant_id", "role")):
            raise ValueError("incomplete claims")
        return claims
    except (jwt.InvalidTokenError, ValueError) as error:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid access token") from error


def require_roles(*allowed: Role):
    """Create a dependency that enforces least-privilege role access."""
    def dependency(claims: dict[str, str] = Depends(current_claims)) -> dict[str, str]:
        if claims["role"] not in {role.value for role in allowed}:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return claims

    return dependency
