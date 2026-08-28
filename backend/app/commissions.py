"""Deterministic multi-level IB commission calculations."""

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import IBRebateRule, IbPartner, LedgerEntry, LedgerEntryType, User, Wallet


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
) -> list[CommissionResult]:
    """Allocate configured tier rebates atomically and journal every wallet credit.

    ``trade_reference`` should be the immutable provider trade/position identifier.
    It makes retries idempotent because each parent-tier ledger reference is unique.
    """
    if lots_traded <= 0:
        raise ValueError("lots_traded must be positive")
    rule = await db.scalar(select(IBRebateRule).where(IBRebateRule.tenant_id == tenant_id))
    trader = await db.scalar(select(User).where(User.id == trader_id, User.tenant_id == tenant_id))
    if not rule or not trader:
        return []
    rates = rule.tier_rates.get(asset_class, rule.tier_rates) if isinstance(rule.tier_rates, dict) else {}
    reference_root = trade_reference or str(uuid4())
    parent_id = trader.parent_ib_id
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
        raw_rate = rates.get(str(tier), 0) if isinstance(rates, dict) else 0
        amount = (lots_traded * Decimal(str(raw_rate))).quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)
        if amount > 0:
            wallet = await db.scalar(select(Wallet).where(Wallet.user_id == parent.id, Wallet.tenant_id == tenant_id, Wallet.currency == "USD").with_for_update())
            if wallet:
                ledger_reference = f"rebate:{reference_root}:{parent.id}:{tier}"
                existing = await db.scalar(select(LedgerEntry).where(LedgerEntry.reference == ledger_reference))
                if not existing:
                    wallet.balance += amount
                    db.add(LedgerEntry(wallet_id=wallet.id, entry_type=LedgerEntryType.COMMISSION, amount=amount, reference=ledger_reference, note=f"Tier {tier} {asset_class} trade rebate"))
                    results.append(CommissionResult(parent.id, tier, amount))
        parent_id = parent.parent_ib_id
        tier += 1
    if tier > 100:
        raise ValueError("IB hierarchy exceeds the 100-level safety limit")
    await db.commit()
    return results
