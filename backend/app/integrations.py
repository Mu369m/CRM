"""Provider-neutral integration contracts for trading and payment systems."""

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from .models import Role


@dataclass(frozen=True, slots=True)
class TradingAccountRequest:
    """Validated account provisioning input shared by every connector."""

    login: str
    server: str
    leverage: int
    is_demo: bool


@dataclass(frozen=True, slots=True)
class TradingAccountSnapshot:
    """Minimal normalized account state returned to CRM services."""

    login: str
    balance: Decimal
    equity: Decimal
    margin_level: Decimal | None
    is_locked: bool


class TradingConnector(Protocol):
    """Adapter contract; concrete MT4/MT5/cTrader clients stay outside domain logic."""

    async def create_account(self, request: TradingAccountRequest) -> TradingAccountSnapshot: ...
    async def set_leverage(self, login: str, leverage: int) -> None: ...
    async def lock_account(self, login: str, locked: bool) -> None: ...
    async def get_snapshot(self, login: str) -> TradingAccountSnapshot: ...


class PaymentGateway(Protocol):
    """Gateway contract with idempotency enforced by the CRM before invocation."""

    async def create_deposit(self, amount: Decimal, currency: str, idempotency_key: str) -> str: ...
    async def create_withdrawal(self, amount: Decimal, currency: str, idempotency_key: str) -> str: ...
    async def verify_webhook(self, body: bytes, signature: str) -> bool: ...


ROLE_PERMISSIONS: dict[Role, frozenset[str]] = {
    Role.SUPER_ADMIN: frozenset({"*"}),
    Role.COMPLIANCE: frozenset({"kyc.read", "kyc.review", "clients.read"}),
    Role.FINANCE: frozenset({"wallet.read", "wallet.adjust", "withdrawal.review"}),
    Role.SALES: frozenset({"clients.read", "ib.read", "ib.manage"}),
    Role.TRADER: frozenset({"wallet.read", "account.read", "kyc.submit"}),
}
