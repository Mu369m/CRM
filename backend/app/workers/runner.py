"""Process entry point for the dedicated market-data and risk worker service."""

import asyncio

from redis.asyncio import Redis

from ..config import get_settings
from ..core.db_router import close_tenant_engines, get_tenant_session_factories
from .price_streamer import PriceStreamer
from .risk_executor import RiskExecutor


async def main() -> None:
    settings = get_settings()
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    tenant_factories = await get_tenant_session_factories()
    if not tenant_factories:
        raise RuntimeError("No active tenants are configured")
    workers = [
        worker
        for tenant_id, session_factory in tenant_factories
        for worker in (
            PriceStreamer(session_factory, redis, tenant_id),
            RiskExecutor(session_factory, redis, tenant_id),
        )
    ]
    tasks = [asyncio.create_task(worker.run()) for worker in workers]
    try:
        await asyncio.gather(*tasks)
    finally:
        for worker in workers:
            await worker.stop()
        await asyncio.gather(*tasks, return_exceptions=True)
        await redis.aclose()
        await close_tenant_engines()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
