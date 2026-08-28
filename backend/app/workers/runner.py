"""Process entry point for the dedicated market-data and risk worker service."""

import asyncio

from redis.asyncio import Redis

from ..config import get_settings
from ..db import SessionFactory
from .price_streamer import PriceStreamer
from .risk_executor import RiskExecutor


async def main() -> None:
    settings = get_settings()
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    price_streamer = PriceStreamer(SessionFactory, redis)
    risk_executor = RiskExecutor(SessionFactory, redis)
    tasks = [asyncio.create_task(price_streamer.run()), asyncio.create_task(risk_executor.run())]
    try:
        await asyncio.gather(*tasks)
    finally:
        await price_streamer.stop()
        await risk_executor.stop()
        await asyncio.gather(*tasks, return_exceptions=True)
        await redis.aclose()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
