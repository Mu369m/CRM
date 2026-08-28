"""Safe MT4/MT5/cTrader manager adapter boundary.

The native Manager API is vendor-specific and normally supplied as a broker SDK or
private gateway. This module validates and decrypts credentials, then requires a
registered transport before any live operation is attempted.
"""

from dataclasses import dataclass
from decimal import Decimal
from collections.abc import Awaitable, Callable
from typing import Protocol

from pydantic import BaseModel, EmailStr, Field

from .crypto import decrypt_field


class MTAccountCreateSchema(BaseModel):
    """Validated trader account provisioning request."""

    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    group: str = Field(min_length=1, max_length=120)
    leverage: int = Field(default=100, ge=1, le=2000)
    deposit: Decimal = Field(default=Decimal("0"), ge=0, max_digits=20, decimal_places=8)


class MTTick(BaseModel):
    """Normalized bid/ask tick emitted by an MT4/MT5 transport."""

    symbol: str = Field(min_length=1, max_length=32)
    bid: Decimal = Field(gt=0, max_digits=20, decimal_places=8)
    ask: Decimal = Field(gt=0, max_digits=20, decimal_places=8)


class MTTradeEvent(BaseModel):
    """Normalized trade event forwarded to the position synchronizer."""

    event_type: str = Field(min_length=1, max_length=40)
    account_login: str = Field(min_length=1, max_length=80)
    symbol: str = Field(min_length=1, max_length=32)
    payload: dict[str, str | int | Decimal | bool] = Field(default_factory=dict)


class ManagerOperations(Protocol):
    """Broker-owned implementation backed by an MT Manager SDK or gateway."""

    async def create_account(self, credentials: dict[str, str], request: MTAccountCreateSchema) -> dict[str, str | Decimal]: ...
    async def update_balance(self, credentials: dict[str, str], login: int, amount: Decimal, comment: str) -> bool: ...


@dataclass(slots=True)
class MTManagerAdapter:
    """Credential-safe facade that refuses operations without a real transport."""

    encrypted_credentials: str
    manager_ip: str
    operations: ManagerOperations | None = None
    tick_handler: Callable[[MTTick], Awaitable[None]] | None = None
    trade_event_handler: Callable[[MTTradeEvent], Awaitable[None]] | None = None

    def _credentials(self) -> dict[str, str]:
        """Decrypt a JSON credential bundle only at operation time."""
        import json

        value = decrypt_field(self.encrypted_credentials)
        credentials = json.loads(value)
        if not isinstance(credentials, dict) or not all(isinstance(key, str) and isinstance(item, str) for key, item in credentials.items()):
            raise ValueError("Encrypted manager credentials must be a string-keyed JSON object")
        return credentials

    async def create_trading_account(self, data: MTAccountCreateSchema) -> dict[str, str | Decimal]:
        """Delegate account creation to the registered broker transport."""
        if self.operations is None:
            raise RuntimeError("No live MT Manager connector is registered")
        result = await self.operations.create_account(self._credentials(), data)
        if "login" not in result or "master_password" not in result:
            raise RuntimeError("Manager connector returned an incomplete account response")
        return {**result, "server_ip": self.manager_ip}

    async def update_account_balance(self, login: int, amount: Decimal, comment: str = "Deposit") -> bool:
        """Perform a balance mutation only through a registered broker transport."""
        if self.operations is None:
            raise RuntimeError("No live MT Manager connector is registered")
        if amount == 0:
            raise ValueError("Balance adjustment cannot be zero")
        return await self.operations.update_balance(self._credentials(), login, amount, comment)

    async def on_tick(self, symbol: str, bid: Decimal, ask: Decimal) -> None:
        """Forward a validated market tick to the registered position synchronizer."""
        tick = MTTick(symbol=symbol.upper(), bid=bid, ask=ask)
        if self.tick_handler:
            await self.tick_handler(tick)

    async def on_trade_event(self, event: MTTradeEvent | dict[str, object]) -> None:
        """Forward a normalized account event from an external MT socket/SDK."""
        normalized = event if isinstance(event, MTTradeEvent) else MTTradeEvent.model_validate(event)
        if self.trade_event_handler:
            await self.trade_event_handler(normalized)
