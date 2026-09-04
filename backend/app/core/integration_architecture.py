"""Per-broker integration architecture enforcement.

This module enforces the business rule that the SaaS provides integration frameworks,
while each broker provides and owns their own credentials/accounts.

Core rules:
- global master features are separate from broker-level config
- broker plan must allow a feature
- broker must enable the integration
- user must have permission
- no secrets leak in logs or API responses
- integration operations must be scoped by tenant_id/broker_id
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class IntegrationStatus(StrEnum):
    DISABLED = "DISABLED"
    NOT_CONFIGURED = "NOT_CONFIGURED"
    TESTING = "TESTING"
    CONNECTED = "CONNECTED"
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    INVALID_CONFIGURATION = "INVALID_CONFIGURATION"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    TIMEOUT = "TIMEOUT"
    EXPIRED_CREDENTIAL = "EXPIRED_CREDENTIAL"
    AUTHENTICATION_REQUIRED = "AUTHENTICATION_REQUIRED"
    CONNECTION_ERROR = "CONNECTION_ERROR"
    CONNECTION_FAILED = "CONNECTION_FAILED"
    ERROR = "ERROR"


class IntegrationProvider(StrEnum):
    MT5 = "MT5"
    MT4 = "MT4"
    STRIPE = "STRIPE"
    PAYPAL = "PAYPAL"
    WISE = "WISE"
    KYC_PROVIDER = "KYC_PROVIDER"
    SMTP = "SMTP"
    TWILIO = "TWILIO"
    WHATSAPP = "WHATSAPP"
    S3 = "S3"
    POSTGRES = "POSTGRES"


@dataclass(frozen=True)
class BrokerIntegrationCheck:
    global_available: bool
    broker_plan_allows: bool
    broker_enabled: bool
    user_permission: bool


def can_use_integration(
    global_available: bool | BrokerIntegrationCheck,
    broker_plan_allows: bool | None = None,
    broker_enabled: bool | None = None,
    user_permission: bool | None = None,
) -> bool:
    """Return whether a tenant may use an integration.

    All four gates must pass:
    1. global feature available
    2. broker plan allows it
    3. broker enabled it
    4. user has permission
    """
    if isinstance(global_available, BrokerIntegrationCheck):
        check = global_available
        return (
            check.global_available
            and check.broker_plan_allows
            and check.broker_enabled
            and check.user_permission
        )

    if None in (broker_plan_allows, broker_enabled, user_permission):
        raise ValueError(
            "broker_plan_allows, broker_enabled, and user_permission are required"
        )

    return (
        bool(global_available)
        and bool(broker_plan_allows)
        and bool(broker_enabled)
        and bool(user_permission)
    )


def mask_secret(value: str | None, visible_tail: int = 4) -> str:
    """Return a masked secret safe for frontend display or logs."""
    if not value:
        return ""
    if len(value) <= visible_tail:
        return "••••"
    reveal_len = max(visible_tail, min(10, len(value)))
    visible = value[-reveal_len:]
    return f"••••••••{visible}"


def integration_scope_ok(broker_id: Any, integration_broker_id: Any) -> bool:
    """Verify a tenant-scoped integration record belongs to the current broker."""
    return str(broker_id) == str(integration_broker_id)


def status_from_connection_result(
    success: bool, *, authentication_required: bool = False
) -> IntegrationStatus:
    """Map provider result to a safe connection status enum."""
    if success:
        return IntegrationStatus.CONNECTED
    if authentication_required:
        return IntegrationStatus.AUTHENTICATION_REQUIRED
    return IntegrationStatus.CONNECTION_FAILED


__all__ = [
    "BrokerIntegrationCheck",
    "IntegrationStatus",
    "IntegrationProvider",
    "can_use_integration",
    "mask_secret",
    "integration_scope_ok",
    "status_from_connection_result",
]
