"""Trader profile and security management endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ....core.db_router import get_tenant_db
from ....models import Role, User
from ....security import require_roles

router = APIRouter(prefix="/api/v1/trader", tags=["Trader Profile"])
TraderClaims = Annotated[dict[str, str], Depends(require_roles(Role.TRADER, Role.IB_PARTNER))]


class ProfilePayload(BaseModel):
    full_name: str | None = Field(default=None, max_length=160)
    phone: str | None = Field(default=None, max_length=40)
    country: str | None = Field(default=None, min_length=2, max_length=2, pattern=r"^[A-Z]{2}$")
    address: str | None = Field(default=None, max_length=500)


class ProfileResponse(ProfilePayload):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    email: str
    role: Role
    kyc_status: str
    is_kyc_verified: bool
    totp_enabled: bool


@router.get("/profile", response_model=ProfileResponse)
async def get_profile(claims: TraderClaims, db: AsyncSession = Depends(get_tenant_db)) -> User:
    user = await db.scalar(select(User).where(User.id == UUID(claims["sub"]), User.tenant_id == UUID(claims["tenant_id"])))
    if not user:
        raise HTTPException(status_code=404, detail="Trader profile not found")
    return user


@router.put("/profile", response_model=ProfileResponse)
async def update_profile(payload: ProfilePayload, claims: TraderClaims, db: AsyncSession = Depends(get_tenant_db)) -> User:
    user = await db.scalar(select(User).where(User.id == UUID(claims["sub"]), User.tenant_id == UUID(claims["tenant_id"])).with_for_update())
    if not user:
        raise HTTPException(status_code=404, detail="Trader profile not found")
    for key, value in payload.model_dump().items(): setattr(user, key, value)
    await db.commit()
    await db.refresh(user)
    return user
