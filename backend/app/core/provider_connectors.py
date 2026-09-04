"""Provider health checks with safe, provider-neutral results."""

from dataclasses import dataclass
import json
from typing import Any

import asyncpg
import httpx

from .integration_architecture import IntegrationStatus


@dataclass(frozen=True)
class ConnectionResult:
    status: IntegrationStatus
    message: str


async def test_provider_connection(
    provider: str,
    integration_type: str,
    config: dict[str, Any],
    encrypted_value: str | None,
    decrypt,
) -> ConnectionResult:
    """Run a non-destructive health check for a supported connector."""
    if not encrypted_value:
        return ConnectionResult(
            IntegrationStatus.AUTHENTICATION_REQUIRED,
            "Credentials are required before testing",
        )
    try:
        raw_credentials = decrypt(encrypted_value)
        credentials = json.loads(raw_credentials)
    except (TypeError, ValueError, json.JSONDecodeError):
        return ConnectionResult(
            IntegrationStatus.CONNECTION_FAILED, "Stored credentials are invalid"
        )
    if not isinstance(credentials, dict) or not credentials:
        return ConnectionResult(
            IntegrationStatus.AUTHENTICATION_REQUIRED,
            "Credentials are required before testing",
        )

    if integration_type.upper() == "HTTP_API":
        endpoint = str(config.get("healthcheck_url", "")).strip()
        if not endpoint.startswith(("https://", "http://")):
            return ConnectionResult(
                IntegrationStatus.ERROR, "A valid provider health-check URL is required"
            )
        token = credentials.get("access_token") or credentials.get("api_key")
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(endpoint, headers=headers)
            if response.status_code in (401, 403):
                return ConnectionResult(
                    IntegrationStatus.AUTHENTICATION_REQUIRED,
                    "Provider rejected the supplied credentials",
                )
            if response.status_code >= 500:
                return ConnectionResult(
                    IntegrationStatus.ERROR, "Provider is temporarily unavailable"
                )
            if response.is_success:
                return ConnectionResult(
                    IntegrationStatus.CONNECTED, "Connection successful"
                )
            return ConnectionResult(
                IntegrationStatus.CONNECTION_FAILED,
                "Provider rejected the connection request",
            )
        except httpx.TimeoutException:
            return ConnectionResult(
                IntegrationStatus.CONNECTION_FAILED, "Provider connection timed out"
            )
        except httpx.RequestError:
            return ConnectionResult(
                IntegrationStatus.CONNECTION_FAILED, "Provider could not be reached"
            )

    if provider.upper() in {"POSTGRES", "POSTGRESQL"}:
        try:
            connection = await asyncpg.connect(
                host=str(config["host"]),
                port=int(config.get("port", 5432)),
                database=str(config["database"]),
                user=str(credentials["username"]),
                password=str(credentials["password"]),
                timeout=5,
            )
            await connection.fetchval("SELECT 1")
            await connection.close()
            return ConnectionResult(
                IntegrationStatus.CONNECTED, "Connection successful"
            )
        except (KeyError, TypeError, ValueError):
            return ConnectionResult(
                IntegrationStatus.ERROR, "Database connection settings are incomplete"
            )
        except asyncpg.InvalidPasswordError:
            return ConnectionResult(
                IntegrationStatus.AUTHENTICATION_REQUIRED,
                "Database rejected the supplied credentials",
            )
        except (asyncpg.PostgresError, OSError, TimeoutError):
            return ConnectionResult(
                IntegrationStatus.CONNECTION_FAILED, "Database could not be reached"
            )

    return ConnectionResult(
        IntegrationStatus.ERROR, f"No connector is configured for provider {provider}"
    )
