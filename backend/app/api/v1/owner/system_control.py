"""Master-owner broadcast controls and public tenant banner read API."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ....db import get_master_db
from ....models.master import SystemBroadcast
from ....security import get_current_owner_user

router = APIRouter(tags=["System Control"])


class BroadcastType(StrEnum):
    MAINTENANCE = "MAINTENANCE"
    URGENT_NEWS = "URGENT_NEWS"
    INFO = "INFO"


class BroadcastTarget(StrEnum):
    ALL_BROKERS = "ALL_BROKERS"
    ENTERPRISE_ONLY = "ENTERPRISE_ONLY"
    PRO_ONLY = "PRO_ONLY"


class BroadcastCreateRequest(BaseModel):
    broadcast_type: BroadcastType = Field(alias="type")
    message: str = Field(min_length=1, max_length=500)
    enabled: bool = False
    target_brokers: BroadcastTarget = BroadcastTarget.ALL_BROKERS

    model_config = ConfigDict(populate_by_name=True)


class BroadcastResponse(BaseModel):
    id: UUID
    type: BroadcastType
    message: str
    enabled: bool
    target_brokers: BroadcastTarget
    timestamp: datetime


def _response(broadcast: SystemBroadcast) -> BroadcastResponse:
    return BroadcastResponse(
        id=broadcast.id,
        type=broadcast.broadcast_type,
        message=broadcast.message,
        enabled=broadcast.enabled,
        target_brokers=broadcast.target_brokers,
        timestamp=broadcast.updated_at or broadcast.created_at,
    )


@router.post("/api/v1/owner/broadcast", response_model=BroadcastResponse, status_code=status.HTTP_201_CREATED)
async def create_broadcast(
    payload: BroadcastCreateRequest,
    db: AsyncSession = Depends(get_master_db),
    _: dict[str, str] = Depends(get_current_owner_user),
) -> BroadcastResponse:
    """Replace the current global banner with a new owner-approved configuration."""
    current = await db.scalar(select(SystemBroadcast).where(SystemBroadcast.enabled.is_(True)))
    if current:
        current.enabled = False
    broadcast = SystemBroadcast(
        broadcast_type=payload.broadcast_type.value,
        message=payload.message.strip(),
        enabled=payload.enabled,
        target_brokers=payload.target_brokers.value,
    )
    db.add(broadcast)
    await db.commit()
    await db.refresh(broadcast)
    return _response(broadcast)


@router.get("/api/v1/owner/broadcast", response_model=BroadcastResponse | None)
async def get_owner_broadcast(
    response: Response,
    db: AsyncSession = Depends(get_master_db),
    _: dict[str, str] = Depends(get_current_owner_user),
) -> BroadcastResponse | None:
    """Return the active global banner for the authenticated master owner."""
    response.headers["Cache-Control"] = "private, max-age=5, stale-while-revalidate=15"
    broadcast = await db.scalar(select(SystemBroadcast).where(SystemBroadcast.enabled.is_(True)).order_by(SystemBroadcast.updated_at.desc()))
    return _response(broadcast) if broadcast else None


@router.get("/api/v1/tenant/broadcast", response_model=BroadcastResponse | None)
async def get_tenant_broadcast(response: Response, db: AsyncSession = Depends(get_master_db)) -> BroadcastResponse | None:
    """Return the active banner for broker dashboards with a short public cache."""
    response.headers["Cache-Control"] = "public, max-age=15, stale-while-revalidate=30"
    broadcast = await db.scalar(select(SystemBroadcast).where(SystemBroadcast.enabled.is_(True)).order_by(SystemBroadcast.updated_at.desc()))
    return _response(broadcast) if broadcast else None