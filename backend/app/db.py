"""Async database and Redis dependency providers."""

from collections.abc import AsyncIterator

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from .config import get_settings

settings = get_settings()
engine = create_async_engine(settings.database_url, pool_pre_ping=True, pool_recycle=1800)
SessionFactory = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncIterator[AsyncSession]:
    """Yield a transaction-scoped session and roll back unhandled request failures."""
    async with SessionFactory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


get_master_db = get_db


async def get_redis() -> AsyncIterator[Redis]:
    """Yield a Redis client; callers own commands, shutdown closes the shared pool."""
    client = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        yield client
    finally:
        await client.aclose()
