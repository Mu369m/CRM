"""FastAPI application entry point for the brokerage CRM."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .api import router as api_router
from .webhooks import router as webhook_router
from .auth_v1 import router as auth_v1_router
from .api_byodb import router as byodb_router

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Application lifecycle hook reserved for connection and worker startup."""
    yield


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "X-Tenant-Host"],
)
app.include_router(api_router)
app.include_router(webhook_router)
app.include_router(auth_v1_router)
app.include_router(byodb_router)


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    """Return a lightweight liveness response without touching business data."""
    return {"status": "healthy", "service": settings.app_name}
