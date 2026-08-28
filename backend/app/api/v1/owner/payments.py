"""SaaS master payment method controls."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ....db import get_db
from ....models import MasterPaymentControl, Role
from ....security import require_roles

router = APIRouter(prefix="/api/v1/owner/payments", tags=["Master Payments"])
Claims = Annotated[dict[str, str], Depends(require_roles(Role.SUPER_ADMIN))]


class MasterPaymentPayload(BaseModel):
    tenant_id: UUID | None = None
    method: str = Field(min_length=2, max_length=30)
    network: str = Field(min_length=2, max_length=30)
    asset: str = Field(min_length=2, max_length=12)
    is_active_master: bool = True


@router.get("/controls")
async def controls(_: Claims, db: AsyncSession = Depends(get_db)):
    return list(await db.scalars(select(MasterPaymentControl).order_by(MasterPaymentControl.method, MasterPaymentControl.network, MasterPaymentControl.asset)))


@router.put("/controls", response_model=MasterPaymentPayload)
async def set_control(payload: MasterPaymentPayload, _: Claims, db: AsyncSession = Depends(get_db)):
    method = await db.scalar(select(MasterPaymentControl).where(MasterPaymentControl.tenant_id == payload.tenant_id, MasterPaymentControl.method == payload.method.upper(), MasterPaymentControl.network == payload.network.upper(), MasterPaymentControl.asset == payload.asset.upper()).with_for_update())
    values = payload.model_dump()
    values.update({"method": payload.method.upper(), "network": payload.network.upper(), "asset": payload.asset.upper()})
    if method:
        for key, value in values.items(): setattr(method, key, value)
    else:
        db.add(MasterPaymentControl(**values))
    await db.commit()
    return payload
