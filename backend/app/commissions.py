"""Deterministic multi-level IB commission calculations."""

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import IbPartner, LedgerEntry, LedgerEntryType, Position, RebateRule, RebateStrategy, User, Wallet


@dataclass(frozen=True, slots=True)
class CommissionResult:
    """Auditable result for one closed trade."""

    partner_id: UUID
    level: int
    amount: Decimal


async def calculate_commission_chain(
    db: AsyncSession,
    tenant_id: UUID,
    referred_user_id: UUID,
    trade_volume_lots: Decimal,
    instrument_revenue: Decimal,
    max_levels: int = 100,
) -> list[CommissionResult]:
    """Walk parent links with cycle and depth protection, never crossing tenants."""
    if trade_volume_lots <= 0 or instrument_revenue < 0:
        raise ValueError("Trade volume must be positive and revenue cannot be negative")
    partner = await db.scalar(select(IbPartner).where(IbPartner.tenant_id == tenant_id, IbPartner.user_id == referred_user_id))
    results: list[CommissionResult] = []
    visited: set[UUID] = set()
    level = 1
    while partner and level <= max_levels:
        if partner.id in visited:
            raise ValueError("IB hierarchy contains a cycle")
        visited.add(partner.id)
        amount = (instrument_revenue * partner.commission_rate).quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)
        results.append(CommissionResult(partner.id, level, amount))
        if not partner.parent_id:
            break
        partner = await db.scalar(select(IbPartner).where(IbPartner.id == partner.parent_id, IbPartner.tenant_id == tenant_id))
        level += 1
    if level > max_levels:
        raise ValueError("IB hierarchy exceeds configured depth limit")
    return results


async def process_trade_rebate(
    db: AsyncSession,
    tenant_id: UUID,
    trader_id: UUID,
    lots_traded: Decimal,
    asset_class: str = "FOREX",
    trade_reference: str | None = None,
    instrument_revenue: Decimal = Decimal("0"),
) -> list[CommissionResult]:
    """Allocate active tenant rebate rules in the caller's transaction."""
    if lots_traded <= 0:
        raise ValueError("lots_traded must be positive")
    if instrument_revenue < 0:
        raise ValueError("instrument_revenue cannot be negative")
    if not trade_reference:
        raise ValueError("trade_reference is required for idempotent rebates")

    try:
        position_id = UUID(trade_reference)
    except ValueError:
        position_id = None
    if position_id:
        await db.scalar(select(Position.id).where(Position.id == position_id).with_for_update())
    already_settled = await db.scalar(
        select(LedgerEntry.id)
        .where(LedgerEntry.reference.like(f"commission:{trade_reference}:%"))
        .limit(1)
    )
    if already_settled:
        return []

    trader = await db.scalar(
        select(User)
        .where(User.id == trader_id, User.tenant_id == tenant_id)
        .with_for_update()
    )
    if not trader:
        return []

    parent_id = trader.parent_ib_id
    if not parent_id:
        partner = await db.scalar(
            select(IbPartner).where(
                IbPartner.user_id == trader_id,
                IbPartner.tenant_id == tenant_id,
            )
        )
        if partner:
            parent_partner = await db.scalar(
                select(IbPartner).where(
                    IbPartner.id == partner.parent_id,
                    IbPartner.tenant_id == tenant_id,
                )
            ) if partner.parent_id else None
            parent_id = parent_partner.user_id if parent_partner else None

    visited: set[UUID] = set()
    results: list[CommissionResult] = []
    tier = 1
    while parent_id and tier <= 100:
        if parent_id in visited:
            raise ValueError("IB hierarchy contains a cycle")
        visited.add(parent_id)
        parent = await db.scalar(select(User).where(User.id == parent_id, User.tenant_id == tenant_id, User.role == "IB_PARTNER"))
        if not parent:
            break
        rule = await db.scalar(
            select(RebateRule)
            .where(
                RebateRule.tenant_id == tenant_id,
                RebateRule.level == tier,
                RebateRule.enabled.is_(True),
                RebateRule.instrument_group == asset_class,
            )
        )
        if not rule:
            parent_id = parent.parent_ib_id
            tier += 1
            continue
        if rule.strategy in {RebateStrategy.PER_LOT_FIXED, RebateStrategy.ASSET_BASED}:
            amount = lots_traded * rule.fixed_per_lot
        else:
            amount = instrument_revenue * rule.spread_percentage / Decimal("100")
        amount = amount.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)
        if amount > 0:
            wallet = await db.scalar(
                select(Wallet)
                .where(
                    Wallet.owner_id == parent.id,
                    Wallet.tenant_id == tenant_id,
                    Wallet.currency == "USD",
                )
                .with_for_update()
            )
            if not wallet:
                wallet = Wallet(tenant_id=tenant_id, owner_id=parent.id, currency="USD", balance=Decimal("0"))
                db.add(wallet)
                await db.flush()
            if wallet:
                ledger_reference = f"commission:{trade_reference}:{parent.id}:{tier}"
                existing = await db.scalar(select(LedgerEntry).where(LedgerEntry.reference == ledger_reference))
                if not existing:
                    wallet.balance += amount
                    db.add(LedgerEntry(wallet_id=wallet.id, entry_type=LedgerEntryType.COMMISSION, amount=amount, reference=ledger_reference, note=f"Tier {tier} {asset_class} trade rebate"))
                    results.append(CommissionResult(parent.id, tier, amount))
        parent_partner = await db.scalar(
            select(IbPartner).where(
                IbPartner.user_id == parent.id,
                IbPartner.tenant_id == tenant_id,
            )
        )
        if parent.parent_ib_id:
            parent_id = parent.parent_ib_id
        elif parent_partner and parent_partner.parent_id:
            next_partner = await db.scalar(
                select(IbPartner).where(
                    IbPartner.id == parent_partner.parent_id,
                    IbPartner.tenant_id == tenant_id,
                )
            )
            parent_id = next_partner.user_id if next_partner else None
        else:
            parent_id = None
        tier += 1
    if tier > 100:
        raise ValueError("IB hierarchy exceeds the 100-level safety limit")
    return results
