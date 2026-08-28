"""Broker position monitoring, risk metrics, and force-close controls."""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ....db import get_db
from ....models import Position, PositionSide, RiskRule, TradeHistory, Wallet
from ....security import require_roles
from ....models import Role

router = APIRouter(prefix="/api/v1/broker/risk", tags=["Broker Risk"])
BrokerClaims = Annotated[dict[str, str], Depends(require_roles(Role.SUPER_ADMIN, Role.BROKER_ADMIN, Role.FINANCE))]


class PositionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    trader_id: UUID
    account_id: UUID
    symbol: str
    volume: Decimal
    side: PositionSide
    open_price: Decimal
    current_price: Decimal
    sl: Decimal | None
    tp: Decimal | None
    floating_pnl: Decimal
    swap: Decimal
    commission: Decimal
    opened_at: datetime
    status: str = "OPEN"


class PositionPage(BaseModel):
    items: list[PositionResponse]
    total: int
    offset: int
    limit: int


class TradeHistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    trader_id: UUID
    account_id: UUID
    symbol: str
    volume: Decimal
    side: PositionSide
    open_price: Decimal
    close_price: Decimal
    realized_pnl: Decimal
    closed_at: datetime
    close_reason: str


class ExposureRow(BaseModel):
    symbol: str
    total_buy_lots: Decimal
    total_sell_lots: Decimal
    net_volume: Decimal


class RiskAccount(BaseModel):
    account_id: UUID
    trader_id: UUID
    equity: Decimal
    margin_usage_percent: Decimal


class RiskMetrics(BaseModel):
    total_equity: Decimal
    total_floating_pnl: Decimal
    margin_usage_percent: Decimal
    accounts_at_risk_stop_out: int
    high_risk_accounts: list[RiskAccount]


class RiskRulePayload(BaseModel):
    max_leverage: int = Field(default=500, ge=1, le=5000)
    margin_call_level: Decimal = Field(default=Decimal("100"), gt=0, le=1000, max_digits=8, decimal_places=4)
    stop_out_level: Decimal = Field(default=Decimal("50"), gt=0, le=1000, max_digits=8, decimal_places=4)
    max_lot_size: Decimal = Field(default=Decimal("100"), gt=0, max_digits=20, decimal_places=8)
    prohibited_symbols_json: list[str] = Field(default_factory=list, max_length=100)
    max_drawdown_alert: Decimal = Field(default=Decimal("20"), gt=0, le=100, max_digits=8, decimal_places=4)

    @model_validator(mode="after")
    def validate_levels(self) -> "RiskRulePayload":
        if self.stop_out_level > self.margin_call_level:
            raise ValueError("stop_out_level cannot exceed margin_call_level")
        if any(symbol != symbol.upper() or not symbol.replace("/", "").replace(".", "").isalnum() for symbol in self.prohibited_symbols_json):
            raise ValueError("prohibited_symbols_json must contain uppercase trading symbols")
        return self


class RiskRuleResponse(RiskRulePayload):
    model_config = ConfigDict(from_attributes=True)
    id: UUID


def calculate_floating_pnl(position: Position) -> Decimal:
    price_delta = position.current_price - position.open_price
    directional_pnl = price_delta * position.volume if position.side == PositionSide.BUY else -price_delta * position.volume
    return directional_pnl + position.swap + position.commission


def position_response(position: Position) -> PositionResponse:
    return PositionResponse(id=position.id, trader_id=position.trader_id, account_id=position.account_id, symbol=position.symbol, volume=position.volume, side=position.side, open_price=position.open_price, current_price=position.current_price, sl=position.sl, tp=position.tp, floating_pnl=calculate_floating_pnl(position), swap=position.swap, commission=position.commission, opened_at=position.opened_at, status="OPEN" if position.is_open else "CLOSED")


@router.get("/positions", response_model=PositionPage)
async def list_positions(
    claims: BrokerClaims,
    db: AsyncSession = Depends(get_db),
    symbol: str | None = Query(default=None, min_length=1, max_length=32),
    account_id: UUID | None = None,
    side: PositionSide | None = None,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> PositionPage:
    filters = [Position.tenant_id == UUID(claims["tenant_id"]), Position.is_open.is_(True)]
    if symbol:
        filters.append(Position.symbol == symbol.upper())
    if account_id:
        filters.append(Position.account_id == account_id)
    if side:
        filters.append(Position.side == side)
    positions = await db.scalars(select(Position).where(*filters).order_by(Position.opened_at.desc()).offset(offset).limit(limit))
    total = await db.scalar(select(func.count(Position.id)).where(*filters))
    return PositionPage(items=[position_response(position) for position in positions], total=total or 0, offset=offset, limit=limit)


@router.get("/exposure", response_model=list[ExposureRow])
async def exposure(claims: BrokerClaims, db: AsyncSession = Depends(get_db)) -> list[ExposureRow]:
    positions = await db.scalars(select(Position).where(Position.tenant_id == UUID(claims["tenant_id"]), Position.is_open.is_(True)))
    grouped: dict[str, list[Decimal]] = {}
    for position in positions:
        values = grouped.setdefault(position.symbol, [Decimal("0"), Decimal("0")])
        values[0 if position.side == PositionSide.BUY else 1] += position.volume
    return [ExposureRow(symbol=symbol, total_buy_lots=values[0], total_sell_lots=values[1], net_volume=values[0] - values[1]) for symbol, values in sorted(grouped.items())]


@router.get("/metrics", response_model=RiskMetrics)
async def metrics(claims: BrokerClaims, db: AsyncSession = Depends(get_db)) -> RiskMetrics:
    tenant_id = UUID(claims["tenant_id"])
    rule = await db.scalar(select(RiskRule).where(RiskRule.tenant_id == tenant_id))
    stop_out_level = rule.stop_out_level if rule else Decimal("50")
    positions = list(await db.scalars(select(Position).where(Position.tenant_id == tenant_id, Position.is_open.is_(True))))
    trader_ids = {position.trader_id for position in positions}
    wallets = list(await db.scalars(select(Wallet).where(Wallet.tenant_id == tenant_id, Wallet.owner_id.in_(trader_ids)))) if trader_ids else []
    equity_by_trader = {wallet.owner_id: wallet.balance for wallet in wallets}
    grouped: dict[UUID, list[Position]] = {}
    for position in positions:
        grouped.setdefault(position.account_id, []).append(position)
    accounts: list[RiskAccount] = []
    for account_id, account_positions in grouped.items():
        trader_id = account_positions[0].trader_id
        equity = equity_by_trader.get(trader_id, Decimal("0"))
        account_notional = sum((position.open_price * position.volume for position in account_positions), Decimal("0"))
        margin_used = account_notional / Decimal("500")
        usage = Decimal("100") if equity <= 0 and margin_used > 0 else (margin_used / equity * Decimal("100") if equity else Decimal("0"))
        accounts.append(RiskAccount(account_id=account_id, trader_id=trader_id, equity=equity, margin_usage_percent=usage.quantize(Decimal("0.01"))))
    at_risk = [account for account in accounts if account.margin_usage_percent >= stop_out_level]
    total_equity = sum((account.equity for account in accounts), Decimal("0"))
    total_floating = sum((calculate_floating_pnl(position) for position in positions), Decimal("0"))
    total_margin = sum(((account.margin_usage_percent / Decimal("100")) * account.equity for account in accounts), Decimal("0"))
    margin_usage = total_margin / total_equity * Decimal("100") if total_equity else Decimal("0")
    return RiskMetrics(total_equity=total_equity, total_floating_pnl=total_floating, margin_usage_percent=margin_usage.quantize(Decimal("0.01")), accounts_at_risk_stop_out=len(at_risk), high_risk_accounts=sorted(at_risk, key=lambda account: account.margin_usage_percent, reverse=True))


@router.post("/positions/{position_id}/close", response_model=TradeHistoryResponse)
async def close_position(position_id: UUID, claims: BrokerClaims, db: AsyncSession = Depends(get_db)) -> TradeHistoryResponse:
    position = await db.scalar(select(Position).where(Position.id == position_id, Position.tenant_id == UUID(claims["tenant_id"]), Position.is_open.is_(True)).with_for_update())
    if not position:
        raise HTTPException(status_code=404, detail="Open position not found")
    now = datetime.now(UTC)
    realized_pnl = calculate_floating_pnl(position)
    position.floating_pnl = realized_pnl
    position.is_open = False
    position.closed_at = now
    history = TradeHistory(tenant_id=position.tenant_id, trader_id=position.trader_id, account_id=position.account_id, symbol=position.symbol, volume=position.volume, side=position.side, open_price=position.open_price, close_price=position.current_price, realized_pnl=realized_pnl, closed_at=now, close_reason="BROKER_FORCE_CLOSE")
    db.add(history)
    await db.commit()
    await db.refresh(history)
    return TradeHistoryResponse.model_validate(history)


@router.get("/rules", response_model=RiskRuleResponse | None)
async def get_rules(claims: BrokerClaims, db: AsyncSession = Depends(get_db)) -> RiskRule | None:
    return await db.scalar(select(RiskRule).where(RiskRule.tenant_id == UUID(claims["tenant_id"])))


@router.post("/rules", response_model=RiskRuleResponse)
async def update_rules(payload: RiskRulePayload, claims: BrokerClaims, db: AsyncSession = Depends(get_db)) -> RiskRule:
    rule = await db.scalar(select(RiskRule).where(RiskRule.tenant_id == UUID(claims["tenant_id"])).with_for_update())
    if not rule:
        rule = RiskRule(tenant_id=UUID(claims["tenant_id"]), **payload.model_dump())
        db.add(rule)
    else:
        for key, value in payload.model_dump().items():
            setattr(rule, key, value)
    await db.commit()
    await db.refresh(rule)
    return rule