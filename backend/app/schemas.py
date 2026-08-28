"""Strict request and response contracts for the public API."""

from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from .models import KycStatus, LedgerEntryType, Role


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    two_factor_code: str | None = Field(default=None, pattern=r"^\d{6}$")


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    role: Role
    kyc_status: KycStatus


class LedgerEntryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    entry_type: LedgerEntryType
    amount: Decimal
    currency: str
    reference: str


class WalletResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    currency: str
    balance: Decimal


class WalletAdjustment(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=20, decimal_places=8)
    entry_type: LedgerEntryType
    reference: str = Field(min_length=8, max_length=120, pattern=r"^[A-Za-z0-9_.:-]+$")
    note: str | None = Field(default=None, max_length=500)


class KycDecision(BaseModel):
    status: KycStatus
    reason: str | None = Field(default=None, max_length=500)
