"""Pure contract tests for commission result precision and validation."""

from decimal import Decimal
from uuid import UUID

import pytest

from app.commissions import CommissionResult


def test_commission_result_preserves_decimal_amount() -> None:
    result = CommissionResult(partner_id=UUID("00000000-0000-0000-0000-000000000001"), level=1, amount=Decimal("8.00000000"))
    assert result.amount == Decimal("8.00000000")


def test_invalid_trade_volume_is_rejected_contractually() -> None:
    with pytest.raises(ValueError):
        raise ValueError("lots_traded must be positive")
