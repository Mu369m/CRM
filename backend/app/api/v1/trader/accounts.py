"""Trader account provisioning request and approval workflow."""

import logging
from enum import StrEnum
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

from ....core.db_router import get_tenant_db
from ....models import AccountPlatform, Role, TradingAccount, Wallet
from ....security import require_roles

router = APIRouter(prefix="/api/v1", tags=["Trading Accounts"])


class ProvisioningStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class AccountRequestPayload(BaseModel):
    platform: AccountPlatform
    is_demo: bool = False
    leverage: int = Field(default=100, ge=1, le=2000)
    server: str = Field(default="", max_length=160)


class AccountApprovalPayload(BaseModel):
    external_login: str = Field(min_length=1, max_length=80)
    server: str = Field(min_length=1, max_length=160)


class AccountProvisionResponse(BaseModel):
    id: UUID
    platform: AccountPlatform
    is_demo: bool
    leverage: int
    provisioning_status: ProvisioningStatus
    wallet_created: bool = False


@router.post("/trader/trading-accounts/request", response_model=AccountProvisionResponse, status_code=status.HTTP_202_ACCEPTED)
async def request_trading_account(
    payload: AccountRequestPayload,
    claims: Annotated[dict[str, str], Depends(require_roles(Role.TRADER))],
    db: AsyncSession = Depends(get_tenant_db),
) -> AccountProvisionResponse:
    account = TradingAccount(tenant_id=UUID(claims["tenant_id"]), user_id=UUID(claims["sub"]), platform=payload.platform, external_login=f"pending-{uuid4()}", server=payload.server or "PENDING", is_demo=payload.is_demo, leverage=payload.leverage, is_locked=True, provisioning_status=ProvisioningStatus.PENDING)
    db.add(account)
    await db.commit()
    await db.refresh(account)
    logger.info(f"Trading account request created: {account.id}, platform={payload.platform}, leverage={payload.leverage}, tenant={claims['tenant_id']}")
    return AccountProvisionResponse(id=account.id, platform=account.platform, is_demo=account.is_demo, leverage=account.leverage, provisioning_status=ProvisioningStatus(account.provisioning_status))


@router.post("/broker/trading-accounts/{account_id}/approve", response_model=AccountProvisionResponse)
async def approve_trading_account(
    account_id: UUID,
    payload: AccountApprovalPayload,
    claims: Annotated[dict[str, str], Depends(require_roles(Role.SUPER_ADMIN, Role.BROKER_ADMIN))],
    db: AsyncSession = Depends(get_tenant_db),
) -> AccountProvisionResponse:
    account = await db.scalar(select(TradingAccount).where(TradingAccount.id == account_id, TradingAccount.tenant_id == UUID(claims["tenant_id"]), TradingAccount.provisioning_status == ProvisioningStatus.PENDING).with_for_update())
    if not account:
        raise HTTPException(status_code=404, detail="Pending trading account request not found")
    account.external_login = payload.external_login
    account.server = payload.server
    account.provisioning_status = ProvisioningStatus.APPROVED
    account.is_locked = False
    logger.info(f"Trading account {account_id} approved: login={payload.external_login}, server={payload.server}, tenant={claims['tenant_id']}")
    wallet = await db.scalar(select(Wallet).where(Wallet.owner_id == account.user_id, Wallet.tenant_id == account.tenant_id).with_for_update())
    wallet_created = wallet is None
    if wallet_created:
        db.add(Wallet(tenant_id=account.tenant_id, owner_id=account.user_id, currency="USD", balance=0))
    await db.commit()
    return AccountProvisionResponse(id=account.id, platform=account.platform, is_demo=account.is_demo, leverage=account.leverage, provisioning_status=ProvisioningStatus.APPROVED, wallet_created=wallet_created)