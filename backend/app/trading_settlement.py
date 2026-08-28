"""Atomic CRM-side trading settlement primitives."""

from decimal import Decimal
from typing import Final

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .commissions import process_trade_rebate
from .models import LedgerEntry, LedgerEntryType, Position, TradeHistory, Wallet

TRADE_SETTLEMENT_REFERENCE_PREFIX: Final[str] = "trade:settlement:"


async def settle_position_closure(
    session: AsyncSession,
    position: Position,
    *,
    close_price: Decimal,
    realized_pnl: Decimal,
    closed_at,
    close_reason: str,
    asset_class: str = "FOREX",
) -> TradeHistory:
    """Close one position and post trader P&L plus IB rebates atomically."""
    wallet = await session.scalar(
        select(Wallet)
        .where(
            Wallet.owner_id == position.trader_id,
            Wallet.tenant_id == position.tenant_id,
            Wallet.currency == "USD",
        )
        .with_for_update()
    )
    if not wallet:
        raise ValueError(f"USD wallet missing for trader {position.trader_id}")
    if wallet.balance + realized_pnl < 0:
        raise ValueError(f"Settlement would make wallet {wallet.id} negative")

    position.floating_pnl = realized_pnl
    position.is_open = False
    position.closed_at = closed_at
    wallet.balance += realized_pnl
    session.add(
        LedgerEntry(
            wallet_id=wallet.id,
            entry_type=LedgerEntryType.TRADE_SETTLEMENT,
            amount=realized_pnl,
            reference=f"{TRADE_SETTLEMENT_REFERENCE_PREFIX}{position.id}",
            note=f"{close_reason} settlement for position {position.id}",
        )
    )
    history = TradeHistory(
        tenant_id=position.tenant_id,
        trader_id=position.trader_id,
        account_id=position.account_id,
        symbol=position.symbol,
        volume=position.volume,
        side=position.side,
        open_price=position.open_price,
        close_price=close_price,
        realized_pnl=realized_pnl,
        closed_at=closed_at,
        close_reason=close_reason,
    )
    session.add(history)
    await process_trade_rebate(
        session,
        position.tenant_id,
        position.trader_id,
        position.volume,
        asset_class=asset_class,
        trade_reference=str(position.id),
        instrument_revenue=max(realized_pnl, Decimal("0")),
    )
    return history

