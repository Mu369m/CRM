"""Market tick ingestion, position mark-to-market, and Redis publication."""

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol
from uuid import UUID

from redis.asyncio import Redis

logger = logging.getLogger(__name__)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..mt_adapter import MTTick
from ..models import Position, PositionSide


@dataclass(frozen=True, slots=True)
class PriceTick:
    symbol: str
    bid: Decimal
    ask: Decimal


class TickSource(Protocol):
    def __aiter__(self) -> AsyncIterator[PriceTick]: ...


def mark_to_market(position: Position, tick: PriceTick) -> Decimal:
    price = tick.bid if position.side == PositionSide.BUY else tick.ask
    delta = price - position.open_price
    directional = delta * position.volume if position.side == PositionSide.BUY else -delta * position.volume
    return directional + position.swap + position.commission


class PriceStreamer:
    """Owns a bounded tick queue and updates all matching open positions atomically."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession], redis: Redis, tenant_id: UUID, queue_size: int = 10_000) -> None:
        self._session_factory = session_factory
        self._redis = redis
        self._tenant_id = tenant_id
        self._ticks: asyncio.Queue[PriceTick] = asyncio.Queue(maxsize=queue_size)
        self._stop = asyncio.Event()
        self._lock = asyncio.Lock()

    async def submit_tick(self, tick: PriceTick) -> None:
        """Enqueue a tick; backpressure prevents unbounded memory growth."""
        await self._ticks.put(PriceTick(symbol=tick.symbol.upper(), bid=tick.bid, ask=tick.ask))

    async def handle_tick(self, tick: MTTick) -> None:
        """Adapter-compatible callback for validated MT ticks."""
        await self.submit_tick(PriceTick(symbol=tick.symbol, bid=tick.bid, ask=tick.ask))

    async def run(self, source: TickSource | None = None) -> None:
        """Consume either an external async source or the adapter-fed queue."""
        source_task = asyncio.create_task(self._consume_source(source)) if source else None
        try:
            while not self._stop.is_set():
                try:
                    tick = await asyncio.wait_for(self._ticks.get(), timeout=1)
                except TimeoutError:
                    continue
                await self._apply_tick(tick)
                self._ticks.task_done()
        finally:
            if source_task:
                source_task.cancel()
                await asyncio.gather(source_task, return_exceptions=True)

    async def _consume_source(self, source: TickSource | None) -> None:
        if not source:
            return
        async for tick in source:
            if self._stop.is_set():
                break
            await self.submit_tick(tick)

    async def _apply_tick(self, tick: PriceTick) -> None:
        lock = self._redis.lock(f"locks:prices:{self._tenant_id}", timeout=60, blocking_timeout=1)
        if not await lock.acquire():
            logger.debug(f"Could not acquire price lock for {tick.symbol} on tenant {self._tenant_id}, skipping this tick")
            return
        try:
            await self._apply_tick_unlocked(tick)
        finally:
            try:
                await lock.release()
            except Exception:
                pass

    async def _apply_tick_unlocked(self, tick: PriceTick) -> None:
        async with self._lock:
            async with self._session_factory() as session:
                positions = list(await session.scalars(select(Position).where(Position.tenant_id == self._tenant_id, Position.symbol == tick.symbol, Position.is_open.is_(True))))
                updates: list[dict[str, str]] = []
                for position in positions:
                    position.current_price = tick.bid if position.side == PositionSide.BUY else tick.ask
                    position.floating_pnl = mark_to_market(position, tick)
                    updates.append({"position_id": str(position.id), "symbol": position.symbol, "floating_pnl": str(position.floating_pnl), "current_price": str(position.current_price)})
                await session.commit()
        if updates:
            logger.debug(f"Updated {len(updates)} positions for symbol {tick.symbol} on tenant {self._tenant_id}")
            await self._redis.publish(f"tenant:{self._tenant_id}:positions:pnl", json.dumps({"type": "position_pnl_updated", "tenant_id": str(self._tenant_id), "updates": updates}))

    async def stop(self) -> None:
        self._stop.set()