"""Validated admin configuration contracts."""

from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from .models import AccountPlatform, RebateStrategy


class RebateRulePayload(BaseModel):
    instrument_group: str = Field(min_length=1, max_length=80)
    strategy: RebateStrategy
    level: int = Field(ge=1, le=100)
    fixed_per_lot: Decimal = Field(ge=0, max_digits=20, decimal_places=8)
    spread_percentage: Decimal = Field(ge=0, le=100, max_digits=12, decimal_places=8)
    asset_class: str | None = Field(default=None, max_length=30)
    enabled: bool = True


class KycRequirementPayload(BaseModel):
    document_type: str = Field(min_length=3, max_length=50)
    required: bool = True
    applies_to_country: str | None = Field(default=None, pattern=r"^[A-Z]{2}$")
    enabled: bool = True


class BonusRulePayload(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    deposit_percentage: Decimal = Field(ge=0, le=100, max_digits=12, decimal_places=8)
    max_credit: Decimal = Field(ge=0, max_digits=20, decimal_places=8)
    withdrawal_lot_target: Decimal = Field(ge=0, max_digits=20, decimal_places=8)
    enabled: bool = True


class ManagerConnectionPayload(BaseModel):
    platform: AccountPlatform
    name: str = Field(min_length=1, max_length=100)
    server: str = Field(min_length=1, max_length=160)
    login: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=256)
    enabled: bool = True


class ManagerConnectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    platform: AccountPlatform
    name: str
    server: str
    login: str
    enabled: bool
