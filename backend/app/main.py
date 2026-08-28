"""FastAPI application entry point for the brokerage CRM."""

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from redis.asyncio import Redis

from .config import get_settings
from .api import router as api_router
from .webhooks import router as webhook_router
from .auth_v1 import router as auth_v1_router
from .api_byodb import router as byodb_router
from .api.v1.owner.system_control import router as system_control_router
from .api.v1.broker.settings import router as broker_settings_router
from .api.v1.trader.accounts import router as trader_accounts_router
from .api.v1.broker.finance import router as finance_router
from .db import SessionFactory
from .api.v1.broker.risk import router as risk_router
from .workers.price_streamer import PriceStreamer
from .workers.risk_executor import RiskExecutor

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start market-data/risk loops and stop them cleanly during shutdown."""
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    price_streamer = PriceStreamer(SessionFactory, redis)
    risk_executor = RiskExecutor(SessionFactory, redis)
    app.state.price_streamer = price_streamer
    app.state.risk_executor = risk_executor
    tasks = [asyncio.create_task(price_streamer.run()), asyncio.create_task(risk_executor.run())]
    try:
        yield
    finally:
        await price_streamer.stop()
        await risk_executor.stop()
        await asyncio.gather(*tasks, return_exceptions=True)
        await redis.aclose()


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "X-Tenant-Host", "X-Tenant-ID"],
)
app.include_router(api_router)
app.include_router(webhook_router)
app.include_router(auth_v1_router)
app.include_router(byodb_router)
app.include_router(system_control_router)
app.include_router(broker_settings_router)
app.include_router(trader_accounts_router)
app.include_router(finance_router)
app.include_router(risk_router)


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    """Return a lightweight liveness response without touching business data."""
    return {"status": "healthy", "service": settings.app_name}
