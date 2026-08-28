"""Broker payment-method configuration and effective availability."""

from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ....core.db_router import get_tenant_db
from ....models import Role, TenantPaymentMethod
from ....security import require_roles

router = APIRouter(prefix="/api/v1/broker/payments", tags=["Broker Payments"])
Claims = Annotated[dict[str, str], Depends(require_roles(Role.SUPER_ADMIN, Role.BROKER_ADMIN, Role.FINANCE))]


class PaymentMethodPayload(BaseModel):
    method: str = Field(min_length=2, max_length=30)
    network: str = Field(min_length=2, max_length=30)
    asset: str = Field(min_length=2, max_length=12)
    chain_id: str | None = Field(default=None, max_length=80)
    contract_address: str | None = Field(default=None, max_length=120)
    deposit_address: str | None = Field(default=None, max_length=200)
    qr_code_url: str | None = Field(default=None, max_length=1000)
    account_details: dict[str, str] = Field(default_factory=dict)
    min_deposit: Decimal = Field(default=Decimal("0"), ge=0)
    max_deposit: Decimal | None = Field(default=None, gt=0)
    min_withdrawal: Decimal = Field(default=Decimal("0"), ge=0)
    processing_fee: Decimal = Field(default=Decimal("0"), ge=0)
    is_active_broker: bool = False


@router.get("/methods")
async def list_methods(claims: Claims, db: AsyncSession = Depends(get_tenant_db)):
    methods = await db.scalars(select(TenantPaymentMethod).where(TenantPaymentMethod.tenant_id == UUID(claims["tenant_id"])).order_by(TenantPaymentMethod.method, TenantPaymentMethod.network, TenantPaymentMethod.asset))
    return list(methods)


@router.put("/methods", response_model=PaymentMethodPayload)
async def upsert_method(payload: PaymentMethodPayload, claims: Claims, db: AsyncSession = Depends(get_tenant_db)):
    tenant_id = UUID(claims["tenant_id"])
    method = await db.scalar(select(TenantPaymentMethod).where(TenantPaymentMethod.tenant_id == tenant_id, TenantPaymentMethod.method == payload.method.upper(), TenantPaymentMethod.network == payload.network.upper(), TenantPaymentMethod.asset == payload.asset.upper()).with_for_update())
    values = payload.model_dump()
    values.update({"tenant_id": tenant_id, "method": payload.method.upper(), "network": payload.network.upper(), "asset": payload.asset.upper()})
    if method:
        for key, value in values.items():
            if key != "tenant_id": setattr(method, key, value)
    else:
        method = TenantPaymentMethod(**values)
        db.add(method)
    await db.commit()
    return payload


@router.delete("/methods/{method_id}")
async def disable_method(method_id: UUID, claims: Claims, db: AsyncSession = Depends(get_tenant_db)):
    method = await db.scalar(select(TenantPaymentMethod).where(TenantPaymentMethod.id == method_id, TenantPaymentMethod.tenant_id == UUID(claims["tenant_id"])).with_for_update())
    if not method: raise HTTPException(status_code=404, detail="Payment method not found")
    method.is_active_broker = False
    await db.commit()
    return {"id": method.id, "is_active_broker": False}
