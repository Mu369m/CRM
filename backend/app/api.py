"""Versioned CRM endpoints with transaction-safe treasury operations."""

from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .db import get_db
from .models import AuditLog, LedgerEntry, Role, User, Wallet
from .schemas import LoginRequest, LedgerEntryResponse, TokenResponse, UserResponse, WalletAdjustment, WalletResponse
from .security import create_access_token, hash_password, require_roles, verify_password

router = APIRouter(prefix="/api")


@router.post("/auth/login", response_model=TokenResponse)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    """Authenticate a user and issue a short-lived bearer token."""
    user = await db.scalar(select(User).where(User.email == payload.email.lower()))
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    token = create_access_token(user.id, user.tenant_id, user.role)
    return TokenResponse(access_token=token, expires_in=900)


@router.get("/me", response_model=UserResponse)
async def me(
    claims: dict[str, str] = Depends(require_roles(*list(Role))),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Expose the authenticated principal without leaking sensitive fields."""
    user = await db.scalar(select(User).where(User.id == UUID(claims["sub"]), User.tenant_id == UUID(claims["tenant_id"])))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.get("/wallet", response_model=WalletResponse)
async def wallet(claims: dict[str, str] = Depends(require_roles(*list(Role))), db: AsyncSession = Depends(get_db)):
    """Return only the wallet belonging to the current tenant principal."""
    wallet = await db.scalar(select(Wallet).where(Wallet.owner_id == UUID(claims["sub"]), Wallet.tenant_id == UUID(claims["tenant_id"])))
    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found")
    return wallet


@router.post("/wallet/adjust", response_model=LedgerEntryResponse)
async def adjust_wallet(
    adjustment: WalletAdjustment,
    claims: dict[str, str] = Depends(require_roles(Role.SUPER_ADMIN, Role.FINANCE)),
    db: AsyncSession = Depends(get_db),
):
    """Atomically lock, validate, update, and journal a wallet adjustment."""
    wallet = await db.scalar(select(Wallet).where(Wallet.owner_id == UUID(claims["sub"]), Wallet.tenant_id == UUID(claims["tenant_id"])).with_for_update())
    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found")
    signed_amount = adjustment.amount if adjustment.entry_type.name in {"DEPOSIT", "COMMISSION", "ADJUSTMENT"} else -adjustment.amount
    if wallet.balance + signed_amount < Decimal("0"):
        raise HTTPException(status_code=409, detail="Insufficient wallet balance")
    wallet.balance += signed_amount
    entry = LedgerEntry(wallet_id=wallet.id, entry_type=adjustment.entry_type, amount=signed_amount, reference=adjustment.reference, note=adjustment.note)
    db.add(entry)
    db.add(AuditLog(tenant_id=wallet.tenant_id, actor_id=UUID(claims["sub"]), action="WALLET_ADJUSTMENT", metadata_json=adjustment.model_dump_json()))
    await db.commit()
    await db.refresh(entry)
    return LedgerEntryResponse(id=entry.id, entry_type=entry.entry_type, amount=entry.amount, currency=wallet.currency, reference=entry.reference)
