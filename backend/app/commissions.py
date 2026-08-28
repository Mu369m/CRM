"""Deterministic multi-level IB commission calculations."""

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import IbPartner


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
