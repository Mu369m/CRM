"""Continuous account margin evaluation and automatic stop-out execution."""

import asyncio
import json
from collections import defaultdict
from datetime import UTC, datetime
from decimal import Decimal

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..models import AuditLog, Position, RiskRule, TradeHistory, Wallet
from .price_streamer import PriceTick, mark_to_market


class RiskExecutor:
    """Evaluate account margin levels and settle stop-outs in one DB transaction."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession], redis: Redis, interval_seconds: float = 5.0) -> None:
        self._session_factory = session_factory
        self._redis = redis
        self._interval = interval_seconds
        self._stop = asyncio.Event()
        self._lock = asyncio.Lock()
        self._alerted_accounts: set[tuple[str, str]] = set()

    async def run(self) -> None:
        while not self._stop.is_set():
            try:
                await self.evaluate_once()
            except Exception:
                # A transient database/provider failure must not kill the long-lived worker.
                await asyncio.sleep(min(self._interval, 5))
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self._interval)
            except TimeoutError:
                pass

    async def evaluate_once(self) -> None:
        async with self._lock:
            async with self._session_factory() as session:
                rules = list(await session.scalars(select(RiskRule)))
                rule_by_tenant = {rule.tenant_id: rule for rule in rules}
                positions = list(await session.scalars(select(Position).where(Position.is_open.is_(True))))
                by_account: dict[tuple[object, object], list[Position]] = defaultdict(list)
                for position in positions:
                    by_account[(position.tenant_id, position.account_id)].append(position)
                for (tenant_id, account_id), account_positions in by_account.items():
                    await self._evaluate_account(session, rule_by_tenant.get(tenant_id), account_id, account_positions)
                await session.commit()

    async def _evaluate_account(self, session: AsyncSession, rule: RiskRule | None, account_id: object, positions: list[Position]) -> None:
        if not rule:
            return
        trader_id = positions[0].trader_id
        wallet = await session.scalar(select(Wallet).where(Wallet.owner_id == trader_id, Wallet.tenant_id == positions[0].tenant_id, Wallet.currency == "USD").with_for_update())
        equity = (wallet.balance if wallet else Decimal("0")) + sum((mark_to_market(position, _position_tick(position)) for position in positions), Decimal("0"))
        margin_used = sum((position.open_price * position.volume / Decimal(rule.max_leverage) for position in positions), Decimal("0"))
        margin_level = Decimal("0") if margin_used <= 0 else equity / margin_used * Decimal("100")
        key = (str(positions[0].tenant_id), str(account_id))
        if margin_level <= rule.stop_out_level:
            for position in positions:
                now = datetime.now(UTC)
                realized = mark_to_market(position, _position_tick(position))
                position.floating_pnl = realized
                position.is_open = False
                position.closed_at = now
                session.add(TradeHistory(tenant_id=position.tenant_id, trader_id=position.trader_id, account_id=position.account_id, symbol=position.symbol, volume=position.volume, side=position.side, open_price=position.open_price, close_price=position.current_price, realized_pnl=realized, closed_at=now, close_reason="STOP_OUT"))
            session.add(AuditLog(tenant_id=positions[0].tenant_id, actor_id=trader_id, action="AUTOMATED_STOP_OUT", metadata_json=json.dumps({"account_id": str(account_id), "margin_level": str(margin_level), "threshold": str(rule.stop_out_level)})))
            self._alerted_accounts.discard(key)
            return
        if margin_level <= rule.margin_call_level and key not in self._alerted_accounts:
            session.add(AuditLog(tenant_id=positions[0].tenant_id, actor_id=trader_id, action="MARGIN_CALL_ALERT", metadata_json=json.dumps({"account_id": str(account_id), "margin_level": str(margin_level), "threshold": str(rule.margin_call_level)})))
            self._alerted_accounts.add(key)
            await self._redis.publish("risk:alerts", json.dumps({"type": "margin_call", "account_id": str(account_id), "margin_level": str(margin_level)}))
        elif margin_level > rule.margin_call_level:
            self._alerted_accounts.discard(key)

    async def stop(self) -> None:
        self._stop.set()


def _position_tick(position: Position):
    """Create a mark using the latest persisted price during risk evaluation."""
    return PriceTick(symbol=position.symbol, bid=position.current_price, ask=position.current_price)