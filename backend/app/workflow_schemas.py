"""Validated workflow contracts for CRM operational modules."""

from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from .models import AccountPlatform, KycStatus, RequestStatus


class TwoFactorSetupResponse(BaseModel):
    secret: str
    provisioning_uri: str


class TwoFactorVerifyRequest(BaseModel):
    code: str = Field(pattern=r"^\d{6}$")


class KycSubmission(BaseModel):
    document_type: str = Field(min_length=3, max_length=50)
    storage_key: str = Field(min_length=1, max_length=500)


class KycReview(BaseModel):
    status: KycStatus
    reason: str | None = Field(default=None, max_length=500)


class MoneyRequestCreate(BaseModel):
    kind: str = Field(pattern=r"^(DEPOSIT|WITHDRAWAL)$")
    amount: Decimal = Field(gt=0, max_digits=20, decimal_places=8)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    idempotency_key: str = Field(min_length=16, max_length=120)


class MoneyRequestResponse(BaseModel):
    id: UUID
    kind: str
    amount: Decimal
    currency: str
    status: RequestStatus
    idempotency_key: str


class TradingAccountCreate(BaseModel):
    platform: AccountPlatform
    external_login: str = Field(min_length=1, max_length=80)
    server: str = Field(min_length=1, max_length=160)
    leverage: int = Field(default=100, ge=1, le=2000)
    is_demo: bool = False
