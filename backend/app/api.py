"""Versioned CRM endpoints with transaction-safe treasury operations."""

from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .db import get_db
from .crypto import decrypt_field, encrypt_field
from .models import AuditLog, KycDocument, LedgerEntry, Role, TradingAccount, User, Wallet
from .schemas import LoginRequest, LedgerEntryResponse, TokenResponse, UserResponse, WalletAdjustment, WalletResponse
from .security import create_access_token, new_totp_secret, require_roles, verify_password, verify_totp
from .workflow_schemas import KycReview, KycSubmission, MoneyRequestCreate, MoneyRequestResponse, TwoFactorSetupResponse, TwoFactorVerifyRequest, TradingAccountCreate

router = APIRouter(prefix="/api")


@router.post("/auth/login", response_model=TokenResponse)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    """Authenticate a user and issue a short-lived bearer token."""
    user = await db.scalar(select(User).where(User.email == payload.email.lower()))
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if user.totp_enabled and (not payload.two_factor_code or not verify_totp(decrypt_field(user.totp_secret_encrypted or ""), payload.two_factor_code)):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Two-factor verification required")
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


@router.post("/auth/2fa/setup", response_model=TwoFactorSetupResponse)
async def setup_2fa(claims: dict[str, str] = Depends(require_roles(*list(Role))), db: AsyncSession = Depends(get_db)):
    """Generate and encrypt a TOTP secret; it becomes active only after verification."""
    user = await db.scalar(select(User).where(User.id == UUID(claims["sub"]), User.tenant_id == UUID(claims["tenant_id"])))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    secret = new_totp_secret()
    user.totp_secret_encrypted = encrypt_field(secret)
    user.totp_enabled = False
    await db.commit()
    return TwoFactorSetupResponse(secret=secret, provisioning_uri=f"otpauth://totp/BrokerageCRM:{user.email}?secret={secret}&issuer=BrokerageCRM")


@router.post("/auth/2fa/verify")
async def verify_2fa(payload: TwoFactorVerifyRequest, claims: dict[str, str] = Depends(require_roles(*list(Role))), db: AsyncSession = Depends(get_db)):
    """Activate TOTP only when the submitted code validates against the encrypted secret."""
    user = await db.scalar(select(User).where(User.id == UUID(claims["sub"]), User.tenant_id == UUID(claims["tenant_id"])))
    if not user or not user.totp_secret_encrypted or not verify_totp(decrypt_field(user.totp_secret_encrypted), payload.code):
        raise HTTPException(status_code=400, detail="Invalid two-factor code")
    user.totp_enabled = True
    await db.commit()
    return {"enabled": True}


@router.post("/kyc/documents")
async def submit_kyc(payload: KycSubmission, claims: dict[str, str] = Depends(require_roles(Role.TRADER)), db: AsyncSession = Depends(get_db)):
    """Submit a storage reference; binary files stay in an external encrypted object store."""
    document = KycDocument(tenant_id=UUID(claims["tenant_id"]), user_id=UUID(claims["sub"]), document_type=payload.document_type, storage_key=payload.storage_key)
    db.add(document)
    await db.commit()
    return {"id": document.id, "status": document.status}


@router.post("/kyc/documents/{document_id}/review")
async def review_kyc(document_id: UUID, payload: KycReview, claims: dict[str, str] = Depends(require_roles(Role.COMPLIANCE, Role.SUPER_ADMIN)), db: AsyncSession = Depends(get_db)):
    """Review only documents inside the caller's tenant and record the decision."""
    document = await db.scalar(select(KycDocument).where(KycDocument.id == document_id, KycDocument.tenant_id == UUID(claims["tenant_id"])))
    if not document:
        raise HTTPException(status_code=404, detail="KYC document not found")
    document.status, document.review_note = payload.status, payload.reason
    await db.commit()
    return {"id": document.id, "status": document.status}


@router.post("/treasury/requests", response_model=MoneyRequestResponse)
async def create_money_request(payload: MoneyRequestCreate, claims: dict[str, str] = Depends(require_roles(*list(Role))), db: AsyncSession = Depends(get_db)):
    """Create an idempotent deposit/withdrawal request for the current principal."""
    from .models import MoneyRequest
    existing = await db.scalar(select(MoneyRequest).where(MoneyRequest.idempotency_key == payload.idempotency_key, MoneyRequest.tenant_id == UUID(claims["tenant_id"])))
    if existing:
        return existing
    request = MoneyRequest(tenant_id=UUID(claims["tenant_id"]), user_id=UUID(claims["sub"]), **payload.model_dump())
    db.add(request)
    await db.commit()
    await db.refresh(request)
    return request


@router.post("/trading-accounts", response_model=dict)
async def register_trading_account(payload: TradingAccountCreate, claims: dict[str, str] = Depends(require_roles(*list(Role))), db: AsyncSession = Depends(get_db)):
    """Persist normalized external account identity before connector synchronization."""
    account = TradingAccount(tenant_id=UUID(claims["tenant_id"]), user_id=UUID(claims["sub"]), **payload.model_dump())
    db.add(account)
    await db.commit()
    await db.refresh(account)
    return {"id": account.id, "platform": account.platform, "external_login": account.external_login, "status": "PENDING_SYNC"}


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
