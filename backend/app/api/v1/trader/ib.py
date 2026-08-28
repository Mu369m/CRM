"""Tenant-scoped IB partner portal APIs."""

from decimal import Decimal
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ....core.db_router import get_tenant_db
from ....models import IbPartner, LedgerEntry, MoneyRequest, Position, Role, User, Wallet
from ....security import require_roles

router = APIRouter(prefix="/api/v1/trader/ib", tags=["Trader IB"])
Claims = Annotated[dict[str, str], Depends(require_roles(Role.TRADER, Role.IB_PARTNER))]


class WithdrawalPayload(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=20, decimal_places=8)
    destination: str = Field(min_length=3, max_length=160)


async def partner_for(db: AsyncSession, claims: dict[str, str]) -> IbPartner:
    partner = await db.scalar(select(IbPartner).where(IbPartner.user_id == UUID(claims["sub"]), IbPartner.tenant_id == UUID(claims["tenant_id"])))
    if not partner:
        raise HTTPException(status_code=404, detail="IB partner profile not found")
    return partner


@router.get("/overview")
async def overview(claims: Claims, db: AsyncSession = Depends(get_tenant_db), x_tenant_host: str | None = Header(default=None, alias="X-Tenant-Host")):
    tenant_id, user_id = UUID(claims["tenant_id"]), UUID(claims["sub"])
    partner = await partner_for(db, claims)
    direct_ids = select(User.id).where(User.parent_ib_id == user_id, User.tenant_id == tenant_id)
    referred = await db.scalar(select(func.count()).select_from(User).where(User.id.in_(direct_ids))) or 0
    volume = await db.scalar(select(func.coalesce(func.sum(Position.volume), 0)).where(Position.trader_id.in_(direct_ids), Position.tenant_id == tenant_id)) or Decimal("0")
    wallet = await db.scalar(select(Wallet).where(Wallet.owner_id == user_id, Wallet.tenant_id == tenant_id, Wallet.currency == "USD"))
    earned = await db.scalar(select(func.coalesce(func.sum(LedgerEntry.amount), 0)).where(LedgerEntry.wallet_id == wallet.id, LedgerEntry.entry_type == "COMMISSION")) if wallet else Decimal("0")
    host = x_tenant_host or "localhost"
    return {"referral_code": partner.referral_code, "referral_link": f"https://{host}/trader/register?ref={partner.referral_code}", "referred_traders": referred, "direct_active_volume": volume, "total_earned_commissions": earned, "wallet_balance": wallet.balance if wallet else Decimal("0")}


@router.get("/network")
async def network(claims: Claims, db: AsyncSession = Depends(get_tenant_db)):
    tenant_id, root_id = UUID(claims["tenant_id"]), UUID(claims["sub"])
    users = list(await db.scalars(select(User).where(User.tenant_id == tenant_id)))
    children: dict[UUID, list[User]] = {}
    for user in users:
        if user.parent_ib_id: children.setdefault(user.parent_ib_id, []).append(user)
    def walk(parent_id: UUID, level: int = 1):
        return [{"id": child.id, "email": child.email, "full_name": child.full_name, "role": child.role, "level": level, "children": walk(child.id, level + 1)} for child in children.get(parent_id, [])]
    return walk(root_id)


@router.get("/commissions")
async def commissions(claims: Claims, db: AsyncSession = Depends(get_tenant_db), offset: int = 0, limit: int = 50):
    wallet = await db.scalar(select(Wallet).where(Wallet.owner_id == UUID(claims["sub"]), Wallet.tenant_id == UUID(claims["tenant_id"]), Wallet.currency == "USD"))
    if not wallet: return {"items": [], "total": 0, "offset": offset, "limit": limit}
    items = list(await db.scalars(select(LedgerEntry).where(LedgerEntry.wallet_id == wallet.id, LedgerEntry.entry_type == "COMMISSION").order_by(LedgerEntry.created_at.desc()).offset(offset).limit(limit)))
    total = await db.scalar(select(func.count(LedgerEntry.id)).where(LedgerEntry.wallet_id == wallet.id, LedgerEntry.entry_type == "COMMISSION"))
    return {"items": items, "total": total or 0, "offset": offset, "limit": limit}


@router.post("/withdraw", status_code=status.HTTP_202_ACCEPTED)
async def withdraw(payload: WithdrawalPayload, claims: Claims, db: AsyncSession = Depends(get_tenant_db)):
    tenant_id, user_id = UUID(claims["tenant_id"]), UUID(claims["sub"])
    wallet = await db.scalar(select(Wallet).where(Wallet.owner_id == user_id, Wallet.tenant_id == tenant_id, Wallet.currency == "USD").with_for_update())
    if not wallet or wallet.balance < payload.amount: raise HTTPException(status_code=409, detail="Insufficient IB wallet balance")
    wallet.balance -= payload.amount
    request = MoneyRequest(tenant_id=tenant_id, user_id=user_id, kind="WITHDRAWAL", amount=payload.amount, currency="USD", status="PENDING", idempotency_key=f"ib-{user_id}-{uuid4()}")
    db.add(request)
    db.add(LedgerEntry(wallet_id=wallet.id, entry_type="WITHDRAWAL", amount=-payload.amount, reference=f"ib-withdrawal:{request.id}", note=payload.destination))
    await db.commit()
    return {"id": request.id, "status": request.status, "amount": payload.amount, "destination": payload.destination}
