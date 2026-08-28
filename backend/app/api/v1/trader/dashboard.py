"""Trader-scoped portfolio, position, history, and ledger APIs."""

from datetime import datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ....core.db_router import get_tenant_db
from ....models import LedgerEntry, Position, PositionSide, Role, TradeHistory, TradingAccount, Wallet
from ....security import require_roles

router = APIRouter(prefix="/api/v1/trader", tags=["Trader Dashboard"])
TraderClaims = Annotated[dict[str, str], Depends(require_roles(Role.TRADER, Role.IB_PARTNER))]


def pnl(position: Position) -> Decimal:
    delta = position.current_price - position.open_price
    return (delta if position.side == PositionSide.BUY else -delta) * position.volume + position.swap + position.commission


@router.get("/portfolio")
async def portfolio(claims: TraderClaims, db: AsyncSession = Depends(get_tenant_db)):
    trader_id = UUID(claims["sub"])
    wallet = await db.scalar(select(Wallet).where(Wallet.owner_id == trader_id, Wallet.tenant_id == UUID(claims["tenant_id"]), Wallet.currency == "USD"))
    accounts = list(await db.scalars(select(TradingAccount).where(TradingAccount.user_id == trader_id, TradingAccount.tenant_id == UUID(claims["tenant_id"])).order_by(TradingAccount.created_at.desc())))
    positions = list(await db.scalars(select(Position).where(Position.trader_id == trader_id, Position.tenant_id == UUID(claims["tenant_id"]), Position.is_open.is_(True))))
    balance = wallet.balance if wallet else Decimal("0")
    floating = sum((pnl(position) for position in positions), Decimal("0"))
    used_margin = sum((position.open_price * position.volume / Decimal("500") for position in positions), Decimal("0"))
    equity = balance + floating
    return {"balance": balance, "equity": equity, "used_margin": used_margin, "free_margin": equity - used_margin, "floating_pnl": floating, "accounts": [{"id": account.id, "platform": account.platform, "login": account.external_login, "server": account.server, "leverage": account.leverage, "is_demo": account.is_demo, "is_locked": account.is_locked, "status": account.provisioning_status} for account in accounts]}


@router.get("/positions")
async def positions(claims: TraderClaims, db: AsyncSession = Depends(get_tenant_db)):
    items = await db.scalars(select(Position).where(Position.trader_id == UUID(claims["sub"]), Position.tenant_id == UUID(claims["tenant_id"]), Position.is_open.is_(True)).order_by(Position.opened_at.desc()))
    return [{"id": p.id, "account_id": p.account_id, "symbol": p.symbol, "side": p.side, "volume": p.volume, "open_price": p.open_price, "current_price": p.current_price, "floating_pnl": pnl(p), "opened_at": p.opened_at} for p in items]


@router.get("/history")
async def history(claims: TraderClaims, db: AsyncSession = Depends(get_tenant_db), offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200), from_date: datetime | None = None, to_date: datetime | None = None):
    filters = [TradeHistory.trader_id == UUID(claims["sub"]), TradeHistory.tenant_id == UUID(claims["tenant_id"])]
    if from_date: filters.append(TradeHistory.closed_at >= from_date)
    if to_date: filters.append(TradeHistory.closed_at < to_date)
    items = list(await db.scalars(select(TradeHistory).where(*filters).order_by(TradeHistory.closed_at.desc()).offset(offset).limit(limit)))
    total = await db.scalar(select(func.count(TradeHistory.id)).where(*filters))
    return {"items": items, "total": total or 0, "offset": offset, "limit": limit}


@router.get("/wallet/transactions")
async def wallet_transactions(claims: TraderClaims, db: AsyncSession = Depends(get_tenant_db), offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200)):
    wallet = await db.scalar(select(Wallet).where(Wallet.owner_id == UUID(claims["sub"]), Wallet.tenant_id == UUID(claims["tenant_id"]), Wallet.currency == "USD"))
    if not wallet: return {"items": [], "total": 0, "offset": offset, "limit": limit}
    items = list(await db.scalars(select(LedgerEntry).where(LedgerEntry.wallet_id == wallet.id).order_by(LedgerEntry.created_at.desc()).offset(offset).limit(limit)))
    total = await db.scalar(select(func.count(LedgerEntry.id)).where(LedgerEntry.wallet_id == wallet.id))
    return {"items": items, "total": total or 0, "offset": offset, "limit": limit}
