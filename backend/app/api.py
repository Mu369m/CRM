"""Versioned CRM endpoints with transaction-safe treasury operations."""

from decimal import Decimal
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from .db import get_db, get_redis
from .core.db_router import get_tenant_db
from .crypto import decrypt_field, encrypt_field
from .models import AuditLog, BonusRule, Client, IbPartner, KycDocument, KycRequirement, LedgerEntry, ManagerConnection, MoneyRequest, RebateRule, Role, Tenant, TenantBranding, TenantSettings, TradingAccount, User, Wallet
from .schemas import LoginRequest, LedgerEntryResponse, TokenResponse, UserResponse, WalletAdjustment, WalletResponse
from .security import create_access_token, new_totp_secret, require_roles, verify_password, verify_totp
from .workflow_schemas import KycReview, KycSubmission, MoneyRequestCreate, MoneyRequestResponse, TwoFactorSetupResponse, TwoFactorVerifyRequest, TradingAccountCreate
from .settings_schemas import TenantSettingsPayload
from .admin_schemas import BonusRulePayload, KycRequirementPayload, ManagerConnectionPayload, ManagerConnectionResponse, RebateRulePayload
from .branding_schemas import TenantBrandingResponse
from .mt_adapter import MTAccountCreateSchema, MTManagerAdapter

# Keep the legacy app/api.py router importable while exposing versioned subrouters.
__path__ = [str(Path(__file__).with_name("api"))]

router = APIRouter(prefix="/api")


@router.get("/v1/tenant/config", response_model=TenantBrandingResponse, tags=["tenant"])
async def public_tenant_config(domain: str, db: AsyncSession = Depends(get_db)):
    """Resolve public branding by exact subdomain or custom domain, without auth data."""
    tenant = await db.scalar(select(Tenant).where(Tenant.is_active.is_(True), or_(Tenant.subdomain == domain, Tenant.custom_domain == domain)))
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant domain not found")
    branding = await db.scalar(select(TenantBranding).where(TenantBranding.tenant_id == tenant.id))
    if not branding:
        raise HTTPException(status_code=404, detail="Tenant branding not configured")
    settings = await db.get(TenantSettings, tenant.id)
    return TenantBrandingResponse(company_name=tenant.name, primary_color=branding.primary_color, secondary_color=branding.secondary_color, logo_url=branding.logo_url, favicon_url=branding.favicon_url, meta_title=settings.meta_title if settings else tenant.name, support_email=settings.support_email if settings else None)


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
    db: AsyncSession = Depends(get_tenant_db),
) -> UserResponse:
    """Expose the authenticated principal without leaking sensitive fields."""
    user = await db.scalar(select(User).where(User.id == UUID(claims["sub"]), User.tenant_id == UUID(claims["tenant_id"])))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.post("/auth/2fa/setup", response_model=TwoFactorSetupResponse)
async def setup_2fa(claims: dict[str, str] = Depends(require_roles(*list(Role))), db: AsyncSession = Depends(get_tenant_db)):
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
async def verify_2fa(payload: TwoFactorVerifyRequest, claims: dict[str, str] = Depends(require_roles(*list(Role))), db: AsyncSession = Depends(get_tenant_db)):
    """Activate TOTP only when the submitted code validates against the encrypted secret."""
    user = await db.scalar(select(User).where(User.id == UUID(claims["sub"]), User.tenant_id == UUID(claims["tenant_id"])))
    if not user or not user.totp_secret_encrypted or not verify_totp(decrypt_field(user.totp_secret_encrypted), payload.code):
        raise HTTPException(status_code=400, detail="Invalid two-factor code")
    user.totp_enabled = True
    await db.commit()
    return {"enabled": True}


@router.post("/kyc/documents")
async def submit_kyc(payload: KycSubmission, claims: dict[str, str] = Depends(require_roles(Role.TRADER)), db: AsyncSession = Depends(get_tenant_db)):
    """Submit a storage reference; binary files stay in an external encrypted object store."""
    document = KycDocument(tenant_id=UUID(claims["tenant_id"]), user_id=UUID(claims["sub"]), document_type=payload.document_type, storage_key=payload.storage_key)
    db.add(document)
    await db.commit()
    return {"id": document.id, "status": document.status}


@router.post("/kyc/documents/{document_id}/review")
async def review_kyc(document_id: UUID, payload: KycReview, claims: dict[str, str] = Depends(require_roles(Role.COMPLIANCE, Role.SUPER_ADMIN)), db: AsyncSession = Depends(get_tenant_db)):
    """Review only documents inside the caller's tenant and record the decision."""
    document = await db.scalar(select(KycDocument).where(KycDocument.id == document_id, KycDocument.tenant_id == UUID(claims["tenant_id"])).with_for_update())
    if not document:
        raise HTTPException(status_code=404, detail="KYC document not found")
    document.status, document.review_note = payload.status, payload.reason
    document.reviewed_at = func.now()
    user = await db.scalar(select(User).where(User.id == document.user_id, User.tenant_id == document.tenant_id).with_for_update())
    user.kyc_status = payload.status
    user.is_kyc_verified = payload.status == "APPROVED"
    await db.commit()
    return {"id": document.id, "status": document.status}


@router.post("/treasury/requests", response_model=MoneyRequestResponse)
async def create_money_request(payload: MoneyRequestCreate, claims: dict[str, str] = Depends(require_roles(*list(Role))), db: AsyncSession = Depends(get_tenant_db)):
    """Create an idempotent deposit/withdrawal request for the current principal."""
    existing = await db.scalar(select(MoneyRequest).where(MoneyRequest.idempotency_key == payload.idempotency_key, MoneyRequest.tenant_id == UUID(claims["tenant_id"])))
    if existing:
        return existing
    request = MoneyRequest(tenant_id=UUID(claims["tenant_id"]), user_id=UUID(claims["sub"]), **payload.model_dump())
    db.add(request)
    await db.commit()
    await db.refresh(request)
    return request


@router.post("/trading-accounts", response_model=dict)
async def register_trading_account(payload: TradingAccountCreate, claims: dict[str, str] = Depends(require_roles(*list(Role))), db: AsyncSession = Depends(get_tenant_db)):
    """Persist normalized external account identity before connector synchronization."""
    tenant_id = UUID(claims["tenant_id"])
    existing = await db.scalar(select(TradingAccount).where(TradingAccount.tenant_id == tenant_id, TradingAccount.platform == payload.platform, TradingAccount.external_login == payload.external_login, TradingAccount.server == payload.server))
    if existing:
        return {"id": existing.id, "platform": existing.platform, "external_login": existing.external_login, "status": existing.provisioning_status}
    account = TradingAccount(tenant_id=tenant_id, user_id=UUID(claims["sub"]), **payload.model_dump())
    db.add(account)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        existing = await db.scalar(select(TradingAccount).where(TradingAccount.tenant_id == tenant_id, TradingAccount.platform == payload.platform, TradingAccount.external_login == payload.external_login, TradingAccount.server == payload.server))
        if not existing:
            raise HTTPException(status_code=409, detail="Unable to safely resolve duplicate trading account")
        return {"id": existing.id, "platform": existing.platform, "external_login": existing.external_login, "status": existing.provisioning_status}
    await db.refresh(account)
    return {"id": account.id, "platform": account.platform, "external_login": account.external_login, "status": "PENDING_SYNC"}


@router.get("/operations/summary")
async def operations_summary(claims: dict[str, str] = Depends(require_roles(*list(Role))), db: AsyncSession = Depends(get_tenant_db)):
    """Return tenant-scoped operational counts for the executive dashboard."""
    tenant_id = UUID(claims["tenant_id"])
    clients = await db.scalar(select(func.count(Client.id)).where(Client.tenant_id == tenant_id))
    traders = await db.scalar(select(func.count(User.id)).where(User.tenant_id == tenant_id, User.role == Role.TRADER))
    pending_kyc = await db.scalar(select(func.count(KycDocument.id)).where(KycDocument.tenant_id == tenant_id, KycDocument.status == "PENDING"))
    pending_money = await db.scalar(select(func.count(MoneyRequest.id)).where(MoneyRequest.tenant_id == tenant_id, MoneyRequest.status == "PENDING"))
    return {"clients": clients or 0, "active_traders": traders or 0, "pending_kyc": pending_kyc or 0, "pending_treasury": pending_money or 0}


@router.get("/kyc/queue")
async def kyc_queue(claims: dict[str, str] = Depends(require_roles(Role.COMPLIANCE, Role.SUPER_ADMIN)), db: AsyncSession = Depends(get_tenant_db)):
    """List only pending documents in the reviewer's tenant."""
    documents = await db.scalars(select(KycDocument).where(KycDocument.tenant_id == UUID(claims["tenant_id"]), KycDocument.status == "PENDING").order_by(KycDocument.created_at))
    return [{"id": item.id, "user_id": item.user_id, "document_type": item.document_type, "created_at": item.created_at} for item in documents]


@router.get("/settings", response_model=TenantSettingsPayload)
async def tenant_settings(claims: dict[str, str] = Depends(require_roles(*list(Role))), db: AsyncSession = Depends(get_tenant_db), redis=Depends(get_redis)):
    """Return runtime branding/rule settings, preferring the hot Redis snapshot."""
    cache_key = f"tenant-settings:{claims['tenant_id']}"
    cached = await redis.get(cache_key)
    if cached:
        return TenantSettingsPayload.model_validate_json(cached)
    settings = await db.get(TenantSettings, UUID(claims["tenant_id"]))
    if not settings:
        raise HTTPException(status_code=404, detail="Tenant settings not found")
    payload = TenantSettingsPayload.model_validate(settings)
    await redis.set(cache_key, payload.model_dump_json(), ex=300)
    return payload


@router.put("/settings", response_model=TenantSettingsPayload)
async def update_tenant_settings(payload: TenantSettingsPayload, claims: dict[str, str] = Depends(require_roles(Role.SUPER_ADMIN)), db: AsyncSession = Depends(get_tenant_db), redis=Depends(get_redis)):
    """Persist tenant configuration and invalidate the hot cache atomically after commit."""
    settings = await db.get(TenantSettings, UUID(claims["tenant_id"]))
    if not settings:
        settings = TenantSettings(tenant_id=UUID(claims["tenant_id"]), **payload.model_dump())
        db.add(settings)
    else:
        for key, value in payload.model_dump().items():
            setattr(settings, key, value)
    await db.commit()
    await redis.delete(f"tenant-settings:{claims['tenant_id']}")
    return payload


@router.put("/admin/rebate-rules", response_model=RebateRulePayload)
async def upsert_rebate_rule(payload: RebateRulePayload, claims: dict[str, str] = Depends(require_roles(Role.SUPER_ADMIN)), db: AsyncSession = Depends(get_tenant_db)):
    """Upsert a runtime rebate rule within the authenticated tenant boundary."""
    tenant_id = UUID(claims["tenant_id"])
    rule = await db.scalar(select(RebateRule).where(RebateRule.tenant_id == tenant_id, RebateRule.instrument_group == payload.instrument_group, RebateRule.level == payload.level))
    if rule:
        for key, value in payload.model_dump().items():
            setattr(rule, key, value)
    else:
        db.add(RebateRule(tenant_id=tenant_id, **payload.model_dump()))
    await db.commit()
    return payload


@router.get("/admin/rebate-rules", response_model=list[RebateRulePayload])
async def list_rebate_rules(claims: dict[str, str] = Depends(require_roles(Role.SUPER_ADMIN, Role.SALES)), db: AsyncSession = Depends(get_tenant_db)):
    """List tenant rebate rules for review and partner operations."""
    rules = await db.scalars(select(RebateRule).where(RebateRule.tenant_id == UUID(claims["tenant_id"])).order_by(RebateRule.level, RebateRule.instrument_group))
    return list(rules)


@router.put("/admin/kyc-requirements", response_model=KycRequirementPayload)
async def upsert_kyc_requirement(payload: KycRequirementPayload, claims: dict[str, str] = Depends(require_roles(Role.SUPER_ADMIN, Role.COMPLIANCE)), db: AsyncSession = Depends(get_tenant_db)):
    """Upsert a country-aware KYC document requirement."""
    tenant_id = UUID(claims["tenant_id"])
    requirement = await db.scalar(select(KycRequirement).where(KycRequirement.tenant_id == tenant_id, KycRequirement.document_type == payload.document_type))
    if requirement:
        for key, value in payload.model_dump().items():
            setattr(requirement, key, value)
    else:
        db.add(KycRequirement(tenant_id=tenant_id, **payload.model_dump()))
    await db.commit()
    return payload


@router.put("/admin/bonus-rules", response_model=BonusRulePayload)
async def upsert_bonus_rule(payload: BonusRulePayload, claims: dict[str, str] = Depends(require_roles(Role.SUPER_ADMIN, Role.FINANCE)), db: AsyncSession = Depends(get_tenant_db)):
    """Upsert deposit bonus and withdrawal volume target rules."""
    db.add(BonusRule(tenant_id=UUID(claims["tenant_id"]), **payload.model_dump()))
    await db.commit()
    return payload


@router.post("/admin/manager-connections", response_model=ManagerConnectionResponse)
async def create_manager_connection(payload: ManagerConnectionPayload, claims: dict[str, str] = Depends(require_roles(Role.SUPER_ADMIN)), db: AsyncSession = Depends(get_tenant_db)):
    """Store provider credentials encrypted; only normalized metadata leaves the API."""
    import json
    credentials = json.dumps({"username": payload.username or payload.login, "password": payload.password})
    connection = ManagerConnection(tenant_id=UUID(claims["tenant_id"]), platform=payload.platform, name=payload.name, server=payload.server, login=payload.login, encrypted_password=encrypt_field(credentials), enabled=payload.enabled)
    db.add(connection)
    await db.commit()
    await db.refresh(connection)
    return connection


@router.get("/admin/manager-connections", response_model=list[ManagerConnectionResponse])
async def list_manager_connections(claims: dict[str, str] = Depends(require_roles(Role.SUPER_ADMIN, Role.FINANCE)), db: AsyncSession = Depends(get_tenant_db)):
    """List manager metadata without exposing encrypted credentials."""
    connections = await db.scalars(select(ManagerConnection).where(ManagerConnection.tenant_id == UUID(claims["tenant_id"])).order_by(ManagerConnection.created_at.desc()))
    return list(connections)


@router.post("/admin/manager-connections/{connection_id}/accounts", status_code=status.HTTP_202_ACCEPTED)
async def create_external_account(
    connection_id: UUID,
    payload: MTAccountCreateSchema,
    claims: dict[str, str] = Depends(require_roles(Role.SUPER_ADMIN, Role.BROKER_ADMIN)),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Queue account provisioning only when a concrete broker transport is registered."""
    connection = await db.scalar(select(ManagerConnection).where(ManagerConnection.id == connection_id, ManagerConnection.tenant_id == UUID(claims["tenant_id"]), ManagerConnection.enabled.is_(True)))
    if not connection:
        raise HTTPException(status_code=404, detail="Enabled manager connection not found")
    adapter = MTManagerAdapter(connection.encrypted_password, connection.server)
    try:
        return await adapter.create_trading_account(payload)
    except RuntimeError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)) from error


@router.get("/wallet", response_model=WalletResponse)
async def wallet(claims: dict[str, str] = Depends(require_roles(*list(Role))), db: AsyncSession = Depends(get_tenant_db)):
    """Return only the wallet belonging to the current tenant principal."""
    wallet = await db.scalar(select(Wallet).where(Wallet.owner_id == UUID(claims["sub"]), Wallet.tenant_id == UUID(claims["tenant_id"])))
    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found")
    return wallet


@router.post("/wallet/adjust", response_model=LedgerEntryResponse)
async def adjust_wallet(
    adjustment: WalletAdjustment,
    claims: dict[str, str] = Depends(require_roles(Role.SUPER_ADMIN, Role.FINANCE)),
    db: AsyncSession = Depends(get_tenant_db),
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
