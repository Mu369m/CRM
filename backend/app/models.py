"""Core brokerage CRM persistence models."""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import (
    DateTime,
    ForeignKey,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Declarative metadata shared by Alembic and the application."""


class Role(StrEnum):
    SUPER_ADMIN = "SUPER_ADMIN"
    BROKER_ADMIN = "BROKER_ADMIN"
    COMPLIANCE = "COMPLIANCE"
    FINANCE = "FINANCE"
    SALES = "SALES"
    IB_PARTNER = "IB_PARTNER"
    TRADER = "TRADER"


class KycStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class LedgerEntryType(StrEnum):
    DEPOSIT = "DEPOSIT"
    WITHDRAWAL = "WITHDRAWAL"
    TRANSFER = "TRANSFER"
    COMMISSION = "COMMISSION"
    TRADE_SETTLEMENT = "TRADE_SETTLEMENT"
    ADJUSTMENT = "ADJUSTMENT"


class RequestStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"


class TransactionType(StrEnum):
    DEPOSIT = "DEPOSIT"
    WITHDRAWAL = "WITHDRAWAL"
    INTERNAL_TRANSFER = "INTERNAL_TRANSFER"


class TransactionStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class PaymentGatewayType(StrEnum):
    CRYPTO = "CRYPTO"
    BANK_WIRE = "BANK_WIRE"
    LOCAL = "LOCAL"


class PositionSide(StrEnum):
    BUY = "BUY"
    SELL = "SELL"


class AccountPlatform(StrEnum):
    MT4 = "MT4"
    MT5 = "MT5"
    CTRADER = "CTRADER"


class RebateType(StrEnum):
    PER_LOT_FIXED = "PER_LOT_FIXED"
    PERCENTAGE_SPREAD = "PERCENTAGE_SPREAD"


class RebateStrategy(StrEnum):
    PER_LOT_FIXED = "PER_LOT_FIXED"
    PERCENTAGE_SPREAD = "PERCENTAGE_SPREAD"
    ASSET_BASED = "ASSET_BASED"


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    name: Mapped[str] = mapped_column(String(160))
    subdomain: Mapped[str | None] = mapped_column(
        String(50), unique=True, index=True, nullable=True
    )
    custom_domain: Mapped[str | None] = mapped_column(
        String(160), unique=True, nullable=True
    )
    is_active: Mapped[bool] = mapped_column(default=True)
    plan: Mapped[str] = mapped_column(String(30), default="STARTER", index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    users: Mapped[list["User"]] = relationship(back_populates="tenant")
    wallets: Mapped[list["Wallet"]] = relationship(back_populates="tenant")
    settings: Mapped["TenantSettings | None"] = relationship(
        back_populates="tenant", uselist=False
    )
    branding: Mapped["TenantBranding | None"] = relationship(
        back_populates="tenant", uselist=False
    )


class ViewAsBrokerSessionRecord(Base):
    __tablename__ = "view_as_broker_sessions"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    admin_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="RESTRICT"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class User(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    full_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    country: Mapped[str | None] = mapped_column(String(2), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(default=Role.TRADER)
    kyc_status: Mapped[KycStatus] = mapped_column(default=KycStatus.PENDING)
    is_kyc_verified: Mapped[bool] = mapped_column(default=False)
    parent_ib_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id"), nullable=True, index=True
    )
    totp_secret_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    totp_enabled: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    tenant: Mapped[Tenant] = relationship(back_populates="users")
    wallet: Mapped["Wallet | None"] = relationship(
        back_populates="owner", uselist=False
    )


class Wallet(Base):
    __tablename__ = "wallets"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    owner_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True
    )
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    balance: Mapped[Decimal] = mapped_column(Numeric(20, 8), default=Decimal("0"))
    tenant: Mapped[Tenant] = relationship(back_populates="wallets")
    owner: Mapped[User] = relationship(back_populates="wallet")
    entries: Mapped[list["LedgerEntry"]] = relationship(back_populates="wallet")


class LedgerEntry(Base):
    __tablename__ = "ledger_entries"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    wallet_id: Mapped[UUID] = mapped_column(
        ForeignKey("wallets.id", ondelete="RESTRICT"), index=True
    )
    entry_type: Mapped[LedgerEntryType] = mapped_column()
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    reference: Mapped[str] = mapped_column(String(120), unique=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    wallet: Mapped[Wallet] = relationship(back_populates="entries")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    actor_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True))
    action: Mapped[str] = mapped_column(String(120))
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class WebhookEvent(Base):
    __tablename__ = "webhook_events"
    __table_args__ = (
        UniqueConstraint("provider", "event_id", name="uq_webhook_provider_event"),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    tenant_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True
    )
    provider: Mapped[str] = mapped_column(String(80))
    event_id: Mapped[str] = mapped_column(String(180))
    payload: Mapped[dict] = mapped_column(JSON)
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class KycDocument(Base):
    __tablename__ = "kyc_documents"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    document_type: Mapped[str] = mapped_column(String(50))
    storage_key: Mapped[str] = mapped_column(Text)
    submission_data: Mapped[dict] = mapped_column(JSONB, default=dict)
    status: Mapped[KycStatus] = mapped_column(default=KycStatus.PENDING)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class TradingAccount(Base):
    __tablename__ = "trading_accounts"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "platform",
            "external_login",
            "server",
            name="uq_trading_account_tenant_external",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    platform: Mapped[AccountPlatform] = mapped_column()
    external_login: Mapped[str] = mapped_column(String(80))
    server: Mapped[str] = mapped_column(String(160))
    is_demo: Mapped[bool] = mapped_column(default=False)
    leverage: Mapped[int] = mapped_column(default=100)
    is_locked: Mapped[bool] = mapped_column(default=False)
    trading_enabled: Mapped[bool] = mapped_column(default=True)
    buy_enabled: Mapped[bool] = mapped_column(default=True)
    sell_enabled: Mapped[bool] = mapped_column(default=True)
    ea_enabled: Mapped[bool] = mapped_column(default=True)
    max_lot_size: Mapped[Decimal] = mapped_column(
        Numeric(20, 8), default=Decimal("100")
    )
    max_open_positions: Mapped[int] = mapped_column(default=100)
    provisioning_status: Mapped[str] = mapped_column(String(20), default="PENDING")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class MoneyRequest(Base):
    __tablename__ = "money_requests"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "idempotency_key", name="uq_money_request_tenant_idempotency"
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(20))
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    currency: Mapped[str] = mapped_column(String(3))
    status: Mapped[RequestStatus] = mapped_column(default=RequestStatus.PENDING)
    provider_reference: Mapped[str | None] = mapped_column(String(160), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class PaymentGateway(Base):
    __tablename__ = "payment_gateways"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_payment_gateway_tenant_name"),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(120))
    type: Mapped[PaymentGatewayType] = mapped_column()
    is_active: Mapped[bool] = mapped_column(default=True)
    config_json: Mapped[dict] = mapped_column(JSONB, default=dict)


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "idempotency_key", name="uq_transaction_idempotency"
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    trader_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    type: Mapped[TransactionType] = mapped_column()
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    currency: Mapped[str] = mapped_column(String(3))
    status: Mapped[TransactionStatus] = mapped_column(
        default=TransactionStatus.PENDING, index=True
    )
    gateway_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("payment_gateways.id", ondelete="SET NULL"), nullable=True
    )
    payment_proof_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    rejection_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(120), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Position(Base):
    __tablename__ = "positions"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    trader_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    account_id: Mapped[UUID] = mapped_column(
        ForeignKey("trading_accounts.id", ondelete="CASCADE"), index=True
    )
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    volume: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    side: Mapped[PositionSide] = mapped_column()
    open_price: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    current_price: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    sl: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    tp: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    floating_pnl: Mapped[Decimal] = mapped_column(Numeric(20, 8), default=Decimal("0"))
    swap: Mapped[Decimal] = mapped_column(Numeric(20, 8), default=Decimal("0"))
    commission: Mapped[Decimal] = mapped_column(Numeric(20, 8), default=Decimal("0"))
    opened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    is_open: Mapped[bool] = mapped_column(default=True, index=True)
    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class TradeHistory(Base):
    __tablename__ = "trade_history"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    trader_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    account_id: Mapped[UUID] = mapped_column(
        ForeignKey("trading_accounts.id", ondelete="CASCADE"), index=True
    )
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    volume: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    side: Mapped[PositionSide] = mapped_column()
    open_price: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    close_price: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    realized_pnl: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    closed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    close_reason: Mapped[str] = mapped_column(String(80))


class RiskRule(Base):
    __tablename__ = "risk_rules"
    __table_args__ = (UniqueConstraint("tenant_id", name="uq_risk_rule_tenant"),)

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    max_leverage: Mapped[int] = mapped_column(default=500)
    margin_call_level: Mapped[Decimal] = mapped_column(
        Numeric(8, 4), default=Decimal("100")
    )
    stop_out_level: Mapped[Decimal] = mapped_column(
        Numeric(8, 4), default=Decimal("50")
    )
    max_lot_size: Mapped[Decimal] = mapped_column(
        Numeric(20, 8), default=Decimal("100")
    )
    prohibited_symbols_json: Mapped[list[str]] = mapped_column(JSONB, default=list)
    max_drawdown_alert: Mapped[Decimal] = mapped_column(
        Numeric(8, 4), default=Decimal("20")
    )


class IbPartner(Base):
    __tablename__ = "ib_partners"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    parent_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("ib_partners.id"), nullable=True, index=True
    )
    referral_code: Mapped[str] = mapped_column(String(50), unique=True)
    commission_rate: Mapped[Decimal] = mapped_column(
        Numeric(12, 6), default=Decimal("0")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class TenantSettings(Base):
    __tablename__ = "tenant_settings"

    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), primary_key=True
    )
    primary_color: Mapped[str] = mapped_column(String(20), default="#45b69c")
    secondary_color: Mapped[str] = mapped_column(String(20), default="#1d3430")
    logo_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    favicon_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta_title: Mapped[str] = mapped_column(String(160), default="Brokerage CRM")
    support_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    max_ib_levels: Mapped[int] = mapped_column(default=5)
    tenant_schema: Mapped[str] = mapped_column(String(80), unique=True)
    kyc_schema: Mapped[dict] = mapped_column(JSONB, default=dict)
    tenant: Mapped[Tenant] = relationship(back_populates="settings")


class RebateRule(Base):
    __tablename__ = "rebate_rules"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "instrument_group", "level", name="uq_rebate_rule_scope"
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    instrument_group: Mapped[str] = mapped_column(String(80))
    strategy: Mapped[RebateStrategy] = mapped_column()
    level: Mapped[int] = mapped_column()
    fixed_per_lot: Mapped[Decimal] = mapped_column(Numeric(20, 8), default=Decimal("0"))
    spread_percentage: Mapped[Decimal] = mapped_column(
        Numeric(12, 8), default=Decimal("0")
    )
    asset_class: Mapped[str | None] = mapped_column(String(30), nullable=True)
    enabled: Mapped[bool] = mapped_column(default=True)


class KycRequirement(Base):
    __tablename__ = "kyc_requirements"
    __table_args__ = (
        UniqueConstraint("tenant_id", "document_type", name="uq_kyc_requirement_type"),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    document_type: Mapped[str] = mapped_column(String(50))
    required: Mapped[bool] = mapped_column(default=True)
    applies_to_country: Mapped[str | None] = mapped_column(String(2), nullable=True)
    enabled: Mapped[bool] = mapped_column(default=True)


class BonusRule(Base):
    __tablename__ = "bonus_rules"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(100))
    deposit_percentage: Mapped[Decimal] = mapped_column(
        Numeric(12, 8), default=Decimal("0")
    )
    max_credit: Mapped[Decimal] = mapped_column(Numeric(20, 8), default=Decimal("0"))
    withdrawal_lot_target: Mapped[Decimal] = mapped_column(
        Numeric(20, 8), default=Decimal("0")
    )
    enabled: Mapped[bool] = mapped_column(default=True)


class TenantBranding(Base):
    __tablename__ = "tenant_brandings"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), unique=True
    )
    primary_color: Mapped[str] = mapped_column(String(7), default="#0F172A")
    secondary_color: Mapped[str] = mapped_column(String(7), default="#3B82F6")
    logo_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    favicon_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    tenant: Mapped[Tenant] = relationship(back_populates="branding")


class TenantThemeVersion(Base):
    __tablename__ = "tenant_theme_versions"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    version: Mapped[int] = mapped_column()
    status: Mapped[str] = mapped_column(String(20), default="DRAFT")
    config: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_by: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class IntegrationProvider(StrEnum):
    MT4 = "MT4"
    MT5 = "MT5"
    PAYMENT_GATEWAY = "PAYMENT_GATEWAY"
    KYC_PROVIDER = "KYC_PROVIDER"
    SMTP = "SMTP"
    SMS = "SMS"
    WHATSAPP = "WHATSAPP"
    STORAGE = "STORAGE"
    DATABASE = "DATABASE"
    WEBHOOK = "WEBHOOK"
    OTHER = "OTHER"


class IntegrationStatus(StrEnum):
    DISABLED = "DISABLED"
    NOT_CONFIGURED = "NOT_CONFIGURED"
    TESTING = "TESTING"
    CONNECTED = "CONNECTED"
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    INVALID_CONFIGURATION = "INVALID_CONFIGURATION"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    TIMEOUT = "TIMEOUT"
    EXPIRED_CREDENTIAL = "EXPIRED_CREDENTIAL"
    AUTHENTICATION_REQUIRED = "AUTHENTICATION_REQUIRED"
    CONNECTION_ERROR = "CONNECTION_ERROR"
    CONNECTION_FAILED = "CONNECTION_FAILED"
    ERROR = "ERROR"


class IntegrationConfig(Base):
    __tablename__ = "integration_configs"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "provider", "name", name="uq_integration_tenant_provider_name"
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(120))
    provider: Mapped[IntegrationProvider] = mapped_column()
    integration_type: Mapped[str] = mapped_column(String(80), default="EXTERNAL")
    status: Mapped[str] = mapped_column(
        String(40), default=IntegrationStatus.NOT_CONFIGURED.value
    )
    enabled: Mapped[bool] = mapped_column(default=False)
    is_saas_managed: Mapped[bool] = mapped_column(default=False)
    encrypted_credentials: Mapped[str | None] = mapped_column(Text, nullable=True)
    config_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    last_connected_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class InfrastructureConfig(Base):
    __tablename__ = "infrastructure_configs"
    __table_args__ = (
        UniqueConstraint("tenant_id", "kind", name="uq_infrastructure_tenant_kind"),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(20))
    mode: Mapped[str] = mapped_column(String(20), default="SAAS")
    provider: Mapped[str | None] = mapped_column(String(80), nullable=True)
    engine: Mapped[str | None] = mapped_column(String(40), nullable=True)
    config_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    encrypted_credentials: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(40), default=IntegrationStatus.NOT_CONFIGURED.value
    )
    active: Mapped[bool] = mapped_column(default=False)
    last_error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    last_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class IntegrationEntitlement(Base):
    __tablename__ = "integration_entitlements"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "provider", "name", name="uq_integration_entitlement_scope"
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(120))
    provider: Mapped[IntegrationProvider] = mapped_column()
    global_available: Mapped[bool] = mapped_column(default=False)
    broker_plan_allows: Mapped[bool] = mapped_column(default=False)
    broker_enabled: Mapped[bool] = mapped_column(default=False)
    user_permission: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class MTServerConfig(Base):
    __tablename__ = "mt_server_configs"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    server_name: Mapped[str] = mapped_column(String(100))
    platform_type: Mapped[AccountPlatform] = mapped_column()
    manager_ip: Mapped[str] = mapped_column(String(100))
    encrypted_credentials: Mapped[str] = mapped_column(Text)


class IBRebateRule(Base):
    __tablename__ = "ib_rebate_rules"
    __table_args__ = (
        UniqueConstraint("tenant_id", "rule_name", name="uq_ib_rebate_rule_name"),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    rule_name: Mapped[str] = mapped_column(String(100))
    rebate_type: Mapped[RebateType] = mapped_column()
    tier_rates: Mapped[dict] = mapped_column(
        JSON, default=lambda: {"1": 8.0, "2": 4.0, "3": 2.0}
    )


class ManagerConnection(Base):
    __tablename__ = "manager_connections"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_manager_connection_name"),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    platform: Mapped[AccountPlatform] = mapped_column()
    name: Mapped[str] = mapped_column(String(100))
    server: Mapped[str] = mapped_column(String(160))
    login: Mapped[str] = mapped_column(String(100))
    encrypted_password: Mapped[str] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


# ==== CUSTOM FIELDS SYSTEM ====
class CustomFieldGroup(Base):
    """Group custom fields by category."""

    __tablename__ = "custom_field_groups"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_custom_field_group_name"),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(100))
    entity_type: Mapped[str] = mapped_column(
        String(50), index=True
    )  # "LEAD", "CLIENT", "IB", etc.
    display_order: Mapped[int] = mapped_column(default=0)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    fields: Mapped[list["CustomFieldDefinition"]] = relationship(
        back_populates="group", cascade="all, delete-orphan"
    )


class CustomFieldDefinition(Base):
    """Define custom field schema."""

    __tablename__ = "custom_field_definitions"
    __table_args__ = (UniqueConstraint("tenant_id", "key", name="uq_custom_field_key"),)

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    group_id: Mapped[UUID] = mapped_column(
        ForeignKey("custom_field_groups.id", ondelete="CASCADE"), index=True
    )
    key: Mapped[str] = mapped_column(String(100))  # Unique internal key
    label: Mapped[str] = mapped_column(String(200))  # Display label
    field_type: Mapped[str] = mapped_column(
        String(30)
    )  # TEXT, NUMBER, CURRENCY, DATE, DROPDOWN, CHECKBOX, PHONE, EMAIL, etc.
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_required: Mapped[bool] = mapped_column(default=False)
    is_searchable: Mapped[bool] = mapped_column(default=True)
    is_filterable: Mapped[bool] = mapped_column(default=True)
    is_sortable: Mapped[bool] = mapped_column(default=True)
    display_order: Mapped[int] = mapped_column(default=0)
    default_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    validation_rules: Mapped[dict] = mapped_column(
        JSONB, default=dict
    )  # min, max, pattern, etc.
    options_json: Mapped[list[dict]] = mapped_column(
        JSONB, default=list
    )  # For DROPDOWN, MULTI_SELECT, RADIO
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    group: Mapped[CustomFieldGroup] = relationship(back_populates="fields")
    values: Mapped[list["CustomFieldValue"]] = relationship(
        back_populates="field", cascade="all, delete-orphan"
    )


class CustomFieldValue(Base):
    """Store custom field values for entities."""

    __tablename__ = "custom_field_values"
    __table_args__ = (
        UniqueConstraint("field_id", "entity_id", name="uq_custom_field_value_entity"),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    field_id: Mapped[UUID] = mapped_column(
        ForeignKey("custom_field_definitions.id", ondelete="CASCADE"), index=True
    )
    entity_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), index=True
    )  # LEAD ID, CLIENT ID, IB ID, etc.
    value: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    field: Mapped[CustomFieldDefinition] = relationship(back_populates="values")


# ==== PIPELINE SYSTEM ====
class Pipeline(Base):
    """Define CRM pipeline for a tenant."""

    __tablename__ = "pipelines"
    __table_args__ = (UniqueConstraint("tenant_id", "name", name="uq_pipeline_name"),)

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(120))
    entity_type: Mapped[str] = mapped_column(
        String(50), index=True
    )  # "LEAD", "CLIENT", etc.
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    is_default: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    stages: Mapped[list["PipelineStage"]] = relationship(
        back_populates="pipeline", cascade="all, delete-orphan"
    )


class PipelineStage(Base):
    """Stages within a pipeline."""

    __tablename__ = "pipeline_stages"
    __table_args__ = (
        UniqueConstraint("pipeline_id", "name", name="uq_pipeline_stage_name"),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    pipeline_id: Mapped[UUID] = mapped_column(
        ForeignKey("pipelines.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(100))
    color: Mapped[str] = mapped_column(String(7), default="#6B7280")  # Hex color
    display_order: Mapped[int] = mapped_column(default=0)
    required_fields: Mapped[list[str]] = mapped_column(
        JSONB, default=list
    )  # Field keys required at this stage
    is_terminal: Mapped[bool] = mapped_column(default=False)  # Is this a final stage
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    pipeline: Mapped[Pipeline] = relationship(back_populates="stages")


# ==== DYNAMIC RBAC ====
class DynamicRole(Base):
    """Custom roles per tenant (not hardcoded)."""

    __tablename__ = "dynamic_roles"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_dynamic_role_name"),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(
        String(100)
    )  # "Sales Manager", "Compliance Officer", etc.
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_system: Mapped[bool] = mapped_column(
        default=False
    )  # System roles can't be deleted
    is_default: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    permissions: Mapped[list["DynamicPermission"]] = relationship(
        back_populates="roles",
        secondary="role_permissions",
    )


class DynamicPermission(Base):
    """Granular permissions per tenant."""

    __tablename__ = "dynamic_permissions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_dynamic_permission_code"),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    code: Mapped[str] = mapped_column(
        String(100)
    )  # "leads.create", "clients.edit", "deposits.approve", etc.
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    module: Mapped[str] = mapped_column(
        String(50)
    )  # "LEADS", "CLIENTS", "DEPOSITS", "REPORTS", etc.
    action: Mapped[str] = mapped_column(
        String(50)
    )  # "VIEW", "CREATE", "EDIT", "DELETE", "APPROVE", etc.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    roles: Mapped[list["DynamicRole"]] = relationship(
        back_populates="permissions",
        secondary="role_permissions",
    )


class RolePermission(Base):
    """Mapping between roles and permissions."""

    __tablename__ = "role_permissions"
    __table_args__ = (
        UniqueConstraint("role_id", "permission_id", name="uq_role_permission"),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    role_id: Mapped[UUID] = mapped_column(
        ForeignKey("dynamic_roles.id", ondelete="CASCADE"), index=True
    )
    permission_id: Mapped[UUID] = mapped_column(
        ForeignKey("dynamic_permissions.id", ondelete="CASCADE"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class UserDynamicRole(Base):
    """Assign dynamic roles to users."""

    __tablename__ = "user_dynamic_roles"
    __table_args__ = (UniqueConstraint("user_id", "role_id", name="uq_user_role"),)

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    role_id: Mapped[UUID] = mapped_column(
        ForeignKey("dynamic_roles.id", ondelete="CASCADE"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


# ==== LEAD MANAGEMENT ====
class Lead(Base):
    """Lead entity with custom fields."""

    __tablename__ = "leads"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    email: Mapped[str] = mapped_column(String(320), index=True)
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    country: Mapped[str | None] = mapped_column(String(2), nullable=True)
    source: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )  # "Google", "Facebook", "Referral", etc.
    campaign_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("campaigns.id", ondelete="SET NULL"), nullable=True
    )
    assigned_to_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    pipeline_id: Mapped[UUID] = mapped_column(
        ForeignKey("pipelines.id", ondelete="RESTRICT"), index=True
    )
    stage_id: Mapped[UUID] = mapped_column(
        ForeignKey("pipeline_stages.id", ondelete="RESTRICT"), index=True
    )
    lead_score: Mapped[int] = mapped_column(default=0)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_contact_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    next_followup_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    is_archived: Mapped[bool] = mapped_column(default=False, index=True)
    pipeline: Mapped[Pipeline] = relationship("Pipeline")
    stage: Mapped[PipelineStage] = relationship("PipelineStage")


# ==== DEPARTMENT & TEAM SYSTEM ====
class Department(Base):
    """Departments within a tenant."""

    __tablename__ = "departments"
    __table_args__ = (UniqueConstraint("tenant_id", "name", name="uq_department_name"),)

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    manager_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    teams: Mapped[list["Team"]] = relationship(
        back_populates="department", cascade="all, delete-orphan"
    )


class Team(Base):
    """Teams within departments."""

    __tablename__ = "teams"
    __table_args__ = (UniqueConstraint("department_id", "name", name="uq_team_name"),)

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    department_id: Mapped[UUID] = mapped_column(
        ForeignKey("departments.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    team_lead_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    department: Mapped[Department] = relationship(back_populates="teams")
    members: Mapped[list["TeamMember"]] = relationship(
        back_populates="team", cascade="all, delete-orphan"
    )


class TeamMember(Base):
    """User membership in teams."""

    __tablename__ = "team_members"
    __table_args__ = (UniqueConstraint("user_id", "team_id", name="uq_user_team"),)

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    team_id: Mapped[UUID] = mapped_column(
        ForeignKey("teams.id", ondelete="CASCADE"), index=True
    )
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    team: Mapped[Team] = relationship(back_populates="members")


# ==== CAMPAIGN MANAGEMENT ====
class Campaign(Base):
    """Marketing campaigns."""

    __tablename__ = "campaigns"
    __table_args__ = (UniqueConstraint("tenant_id", "name", name="uq_campaign_name"),)

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(120))
    source: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )  # "Google Ads", "Facebook", etc.
    medium: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )  # "cpc", "organic", "social", etc.
    utm_campaign: Mapped[str | None] = mapped_column(String(100), nullable=True)
    utm_content: Mapped[str | None] = mapped_column(String(100), nullable=True)
    utm_term: Mapped[str | None] = mapped_column(String(100), nullable=True)
    country: Mapped[str | None] = mapped_column(String(2), nullable=True)
    landing_page: Mapped[str | None] = mapped_column(Text, nullable=True)
    start_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    end_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    budget: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    leads: Mapped[list[Lead]] = relationship("Lead")


# ==== TASK & ACTIVITY SYSTEM ====
class Task(Base):
    """Tasks for follow-ups and activities."""

    __tablename__ = "tasks"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    entity_type: Mapped[str] = mapped_column(String(50))  # "LEAD", "CLIENT", etc.
    entity_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    assigned_to_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    priority: Mapped[str] = mapped_column(
        String(20), default="NORMAL"
    )  # LOW, NORMAL, HIGH, URGENT
    status: Mapped[str] = mapped_column(
        String(50), default="PENDING"
    )  # PENDING, IN_PROGRESS, COMPLETED, CANCELLED
    due_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Activity(Base):
    """Activity log for entities."""

    __tablename__ = "activities"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    entity_type: Mapped[str] = mapped_column(
        String(50), index=True
    )  # "LEAD", "CLIENT", etc.
    entity_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), index=True)
    activity_type: Mapped[str] = mapped_column(
        String(50)
    )  # "EMAIL_SENT", "CALL", "NOTE", "STATUS_CHANGE", etc.
    description: Mapped[str] = mapped_column(Text)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Note(Base):
    """Notes attached to entities."""

    __tablename__ = "notes"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    entity_type: Mapped[str] = mapped_column(
        String(50), index=True
    )  # "LEAD", "CLIENT", etc.
    entity_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), index=True)
    content: Mapped[str] = mapped_column(Text)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


# ==== TAGS SYSTEM ====
class Tag(Base):
    """Tags for categorizing entities."""

    __tablename__ = "tags"
    __table_args__ = (UniqueConstraint("tenant_id", "name", name="uq_tag_name"),)

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(50))
    color: Mapped[str] = mapped_column(String(7), default="#6B7280")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class EntityTag(Base):
    """Tags applied to entities."""

    __tablename__ = "entity_tags"
    __table_args__ = (
        UniqueConstraint("entity_type", "entity_id", "tag_id", name="uq_entity_tag"),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    entity_type: Mapped[str] = mapped_column(
        String(50), index=True
    )  # "LEAD", "CLIENT", etc.
    entity_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), index=True)
    tag_id: Mapped[UUID] = mapped_column(
        ForeignKey("tags.id", ondelete="CASCADE"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


# ==== CLIENT MANAGEMENT ====
class Client(Base):
    """Client/trader entity."""

    __tablename__ = "clients"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(320), index=True)
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    country: Mapped[str | None] = mapped_column(String(2), nullable=True)
    trading_platform: Mapped[str | None] = mapped_column(String(50), nullable=True)
    account_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    assigned_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    source: Mapped[str | None] = mapped_column(String(100), nullable=True)
    campaign_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("campaigns.id", ondelete="SET NULL"), nullable=True
    )
    ib_partner_id: Mapped[UUID | None] = mapped_column(nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="NEW", index=True)
    total_deposits: Mapped[Decimal | None] = mapped_column(
        Numeric(19, 2), nullable=True
    )
    total_withdrawals: Mapped[Decimal | None] = mapped_column(
        Numeric(19, 2), nullable=True
    )
    net_deposits: Mapped[Decimal | None] = mapped_column(Numeric(19, 2), nullable=True)
    last_deposit_date: Mapped[datetime | None] = mapped_column(nullable=True)
    last_withdrawal_date: Mapped[datetime | None] = mapped_column(nullable=True)
    is_archived: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ClientAccount(Base):
    """Trading account linked to a client."""

    __tablename__ = "client_accounts"
    __table_args__ = (
        UniqueConstraint("tenant_id", "account_number", name="uq_account_number"),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    client_id: Mapped[UUID] = mapped_column(
        ForeignKey("clients.id", ondelete="CASCADE"), index=True
    )
    account_number: Mapped[str] = mapped_column(String(100))
    platform: Mapped[str] = mapped_column(String(50))  # MT5, MT4, etc.
    server: Mapped[str | None] = mapped_column(String(100), nullable=True)
    trading_status: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )  # Active, Suspended
    account_balance: Mapped[Decimal | None] = mapped_column(
        Numeric(19, 2), nullable=True
    )
    equity: Mapped[Decimal | None] = mapped_column(Numeric(19, 2), nullable=True)
    margin: Mapped[Decimal | None] = mapped_column(Numeric(19, 2), nullable=True)
    free_margin: Mapped[Decimal | None] = mapped_column(Numeric(19, 2), nullable=True)
    leverage: Mapped[int | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ClientFinancials(Base):
    """Cumulative financial data for a client."""

    __tablename__ = "client_financials"
    __table_args__ = (
        UniqueConstraint("tenant_id", "client_id", name="uq_client_financials"),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    client_id: Mapped[UUID] = mapped_column(
        ForeignKey("clients.id", ondelete="CASCADE"), index=True
    )
    total_deposits: Mapped[Decimal] = mapped_column(
        Numeric(19, 2), default=Decimal("0")
    )
    total_withdrawals: Mapped[Decimal] = mapped_column(
        Numeric(19, 2), default=Decimal("0")
    )
    net_deposits: Mapped[Decimal] = mapped_column(Numeric(19, 2), default=Decimal("0"))
    total_trading_volume: Mapped[Decimal] = mapped_column(
        Numeric(19, 2), default=Decimal("0")
    )
    total_commissions_paid: Mapped[Decimal] = mapped_column(
        Numeric(19, 2), default=Decimal("0")
    )
    total_profit_loss: Mapped[Decimal] = mapped_column(
        Numeric(19, 2), default=Decimal("0")
    )
    last_updated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


# ==== IB / AFFILIATE MANAGEMENT ====
class IBPartner(Base):
    """IB/Affiliate partner managing client referrals."""

    __tablename__ = "ib_partners"
    __table_args__ = {"extend_existing": True}

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(320), index=True)
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    company_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    country: Mapped[str | None] = mapped_column(String(2), nullable=True)
    ib_level: Mapped[int] = mapped_column(default=1)
    parent_ib_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("ib_partners.id", ondelete="SET NULL"), nullable=True, index=True
    )
    commission_tier: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="ACTIVE", index=True)
    total_clients: Mapped[int] = mapped_column(default=0)
    total_commissions: Mapped[Decimal] = mapped_column(
        Numeric(19, 2), default=Decimal("0")
    )
    total_deposits_referred: Mapped[Decimal] = mapped_column(
        Numeric(19, 2), default=Decimal("0")
    )
    bank_account: Mapped[str | None] = mapped_column(String(200), nullable=True)
    payment_method: Mapped[str | None] = mapped_column(String(50), nullable=True)
    kyc_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_archived: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class IBRelationship(Base):
    """Links IBs to their referred clients."""

    __tablename__ = "ib_relationships"
    __table_args__ = (
        UniqueConstraint("ib_partner_id", "client_id", name="uq_ib_client"),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    ib_partner_id: Mapped[UUID] = mapped_column(
        ForeignKey("ib_partners.id", ondelete="CASCADE"), index=True
    )
    client_id: Mapped[UUID] = mapped_column(
        ForeignKey("clients.id", ondelete="CASCADE"), index=True
    )
    referred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    status: Mapped[str] = mapped_column(String(50), default="ACTIVE")


class IBCommission(Base):
    """Commission rates and rules for IBs."""

    __tablename__ = "ib_commissions"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    ib_partner_id: Mapped[UUID] = mapped_column(
        ForeignKey("ib_partners.id", ondelete="CASCADE"), index=True
    )
    commission_type: Mapped[str] = mapped_column(
        String(50)
    )  # "DEPOSIT", "SPREAD", "VOLUME", etc.
    base_rate: Mapped[Decimal] = mapped_column(Numeric(10, 4))
    tier_level: Mapped[int | None] = mapped_column(nullable=True)
    min_turnover: Mapped[Decimal | None] = mapped_column(Numeric(19, 2), nullable=True)
    max_turnover: Mapped[Decimal | None] = mapped_column(Numeric(19, 2), nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True)


# ==== WORKFLOWS & AUTOMATION ====
class Workflow(Base):
    """Workflow automation engine for business processes."""

    __tablename__ = "workflows"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(200), unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    entity_type: Mapped[str] = mapped_column(
        String(50), index=True
    )  # 'lead', 'client', 'deposit'
    is_active: Mapped[bool] = mapped_column(default=True, index=True)
    trigger_type: Mapped[str] = mapped_column(
        String(50)
    )  # 'entity_created', 'status_changed', 'time_based'
    trigger_config: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class WorkflowAction(Base):
    """Actions to execute when workflow is triggered."""

    __tablename__ = "workflow_actions"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    workflow_id: Mapped[UUID] = mapped_column(
        ForeignKey("workflows.id", ondelete="CASCADE"), index=True
    )
    action_type: Mapped[str] = mapped_column(
        String(50)
    )  # 'send_notification', 'assign_lead', 'create_task', 'update_field', 'send_email'
    action_config: Mapped[dict] = mapped_column(JSONB, default=dict)
    order: Mapped[int] = mapped_column(default=0, index=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class WorkflowCondition(Base):
    """Conditional logic for workflow execution."""

    __tablename__ = "workflow_conditions"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    workflow_id: Mapped[UUID] = mapped_column(
        ForeignKey("workflows.id", ondelete="CASCADE"), index=True
    )
    field_name: Mapped[str] = mapped_column(String(100))
    operator: Mapped[str] = mapped_column(
        String(50)
    )  # 'equals', 'contains', 'greater_than', 'less_than', 'is_empty'
    value: Mapped[str | None] = mapped_column(String(500), nullable=True)
    logic_operator: Mapped[str] = mapped_column(
        String(10), default="AND"
    )  # 'AND', 'OR'
    order: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class WorkflowExecution(Base):
    """Tracks workflow execution history."""

    __tablename__ = "workflow_executions"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    workflow_id: Mapped[UUID] = mapped_column(
        ForeignKey("workflows.id", ondelete="CASCADE"), index=True
    )
    entity_id: Mapped[UUID] = mapped_column(index=True)
    entity_type: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(
        String(50), default="PENDING", index=True
    )  # 'PENDING', 'IN_PROGRESS', 'SUCCESS', 'FAILED'
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    execution_data: Mapped[dict] = mapped_column(JSONB, default=dict)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )


class WorkflowActionExecution(Base):
    """Tracks individual action execution within a workflow."""

    __tablename__ = "workflow_action_executions"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    workflow_execution_id: Mapped[UUID] = mapped_column(
        ForeignKey("workflow_executions.id", ondelete="CASCADE"), index=True
    )
    workflow_action_id: Mapped[UUID] = mapped_column(
        ForeignKey("workflow_actions.id", ondelete="CASCADE")
    )
    status: Mapped[str] = mapped_column(
        String(50), default="PENDING", index=True
    )  # 'PENDING', 'SUCCESS', 'FAILED'
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_data: Mapped[dict] = mapped_column(JSONB, default=dict)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    effective_to: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class IBPayout(Base):
    """Commission payouts to IBs."""

    __tablename__ = "ib_payouts"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    ib_partner_id: Mapped[UUID] = mapped_column(
        ForeignKey("ib_partners.id", ondelete="CASCADE"), index=True
    )
    payout_period: Mapped[str] = mapped_column(String(50))  # "2026-08", "2026-Q3", etc.
    total_commissions: Mapped[Decimal] = mapped_column(Numeric(19, 2))
    total_clients_referred: Mapped[int] = mapped_column()
    status: Mapped[str] = mapped_column(String(50), default="PENDING")
    payment_status: Mapped[str] = mapped_column(String(50), default="PENDING")
    payment_date: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


# ==== DEPOSITS & WITHDRAWALS ====
class DepositMethod(Base):
    """Available deposit payment methods."""

    __tablename__ = "deposit_methods"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(200))
    provider: Mapped[str] = mapped_column(
        String(100)
    )  # "Stripe", "Wire Transfer", "Crypto", etc.
    method_type: Mapped[str] = mapped_column(
        String(50)
    )  # "CARD", "BANK", "CRYPTO", "E-WALLET"
    min_amount: Mapped[Decimal | None] = mapped_column(Numeric(19, 2), nullable=True)
    max_amount: Mapped[Decimal | None] = mapped_column(Numeric(19, 2), nullable=True)
    processing_fee_percent: Mapped[Decimal] = mapped_column(
        Numeric(6, 2), default=Decimal("0")
    )
    processing_time_hours: Mapped[int | None] = mapped_column(nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    requires_verification: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Deposit(Base):
    """Client deposit transactions."""

    __tablename__ = "deposits"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    client_id: Mapped[UUID] = mapped_column(
        ForeignKey("clients.id", ondelete="CASCADE"), index=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(19, 2))
    currency: Mapped[str] = mapped_column(String(3))  # USD, EUR, etc.
    method_id: Mapped[UUID] = mapped_column(
        ForeignKey("deposit_methods.id", ondelete="RESTRICT"), index=True
    )
    method_name: Mapped[str] = mapped_column(String(200))
    payment_reference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(
        String(50), default="PENDING", index=True
    )  # PENDING, APPROVED, REJECTED, COMPLETED
    processing_fee: Mapped[Decimal] = mapped_column(
        Numeric(19, 2), default=Decimal("0")
    )
    net_amount: Mapped[Decimal] = mapped_column(Numeric(19, 2))
    approved_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    rejected_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    rejection_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class WithdrawalMethod(Base):
    """Available withdrawal payment methods."""

    __tablename__ = "withdrawal_methods"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(200))
    provider: Mapped[str] = mapped_column(String(100))
    method_type: Mapped[str] = mapped_column(
        String(50)
    )  # "CARD", "BANK", "CRYPTO", "E-WALLET"
    min_amount: Mapped[Decimal | None] = mapped_column(Numeric(19, 2), nullable=True)
    max_amount: Mapped[Decimal | None] = mapped_column(Numeric(19, 2), nullable=True)
    processing_fee_percent: Mapped[Decimal] = mapped_column(
        Numeric(6, 2), default=Decimal("0")
    )
    processing_time_hours: Mapped[int | None] = mapped_column(nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    requires_verification: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Withdrawal(Base):
    """Client withdrawal transactions."""

    __tablename__ = "withdrawals"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    client_id: Mapped[UUID] = mapped_column(
        ForeignKey("clients.id", ondelete="CASCADE"), index=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(19, 2))
    currency: Mapped[str] = mapped_column(String(3))
    method_id: Mapped[UUID] = mapped_column(
        ForeignKey("withdrawal_methods.id", ondelete="RESTRICT"), index=True
    )
    method_name: Mapped[str] = mapped_column(String(200))
    payment_reference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(
        String(50), default="PENDING", index=True
    )  # PENDING, APPROVED, REJECTED, COMPLETED
    processing_fee: Mapped[Decimal] = mapped_column(
        Numeric(19, 2), default=Decimal("0")
    )
    net_amount: Mapped[Decimal] = mapped_column(Numeric(19, 2))
    approved_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    rejected_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    rejection_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


# ==== KYC & DOCUMENT MANAGEMENT ====
class DocumentType(Base):
    """Document types required for KYC."""

    __tablename__ = "document_types"
    __table_args__ = (UniqueConstraint("tenant_id", "name", name="uq_doc_type_name"),)

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    required_for_kyc: Mapped[bool] = mapped_column(default=False)
    max_file_size_mb: Mapped[int] = mapped_column(default=10)
    allowed_formats: Mapped[str] = mapped_column(String(100), default="pdf,jpg,png")
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class KYCDocument(Base):
    """Client KYC documents."""

    __tablename__ = "kyc_documents"
    __table_args__ = {"extend_existing": True}

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    client_id: Mapped[UUID] = mapped_column(
        ForeignKey("clients.id", ondelete="CASCADE"), index=True
    )
    document_type_id: Mapped[UUID] = mapped_column(
        ForeignKey("document_types.id", ondelete="RESTRICT"), index=True
    )
    file_name: Mapped[str] = mapped_column(String(255))
    file_path: Mapped[str] = mapped_column(String(500))
    file_size_bytes: Mapped[int] = mapped_column()
    mime_type: Mapped[str] = mapped_column(String(50))
    uploaded_by: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    status: Mapped[str] = mapped_column(
        String(50), default="PENDING", index=True
    )  # PENDING, APPROVED, REJECTED
    rejection_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    approved_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    rejected_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class KYCApproval(Base):
    """KYC verification workflow and approval status."""

    __tablename__ = "kyc_approvals"
    __table_args__ = (UniqueConstraint("client_id", "kyc_level", name="uq_kyc_level"),)

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    client_id: Mapped[UUID] = mapped_column(
        ForeignKey("clients.id", ondelete="CASCADE"), index=True
    )
    kyc_level: Mapped[str] = mapped_column(
        String(50)
    )  # "BASIC", "INTERMEDIATE", "FULL"
    status: Mapped[str] = mapped_column(String(50), default="PENDING", index=True)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    verified_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    verified_at: Mapped[datetime | None] = mapped_column(nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class FeatureDefinition(Base):
    """Reusable platform feature registered once for all tenants."""

    __tablename__ = "feature_definitions"
    __table_args__ = (
        UniqueConstraint("feature_key", name="uq_feature_definition_key"),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    feature_key: Mapped[str] = mapped_column(String(120), index=True)
    name: Mapped[str] = mapped_column(String(160))
    feature_type: Mapped[str] = mapped_column(String(40), default="MODULE")
    version: Mapped[str] = mapped_column(String(30), default="1.0")
    is_available: Mapped[bool] = mapped_column(default=True, index=True)
    eligible_plans: Mapped[list] = mapped_column(JSONB, default=list)
    pricing_type: Mapped[str] = mapped_column(String(30), default="INCLUDED")
    billable_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(19, 4), nullable=True
    )
    dependency_keys: Mapped[list] = mapped_column(JSONB, default=list)
    conflict_keys: Mapped[list] = mapped_column(JSONB, default=list)
    configuration_schema: Mapped[dict] = mapped_column(JSONB, default=dict)
    internal_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class TenantFeatureGrant(Base):
    """Tenant-specific entitlement, independent from the purchased plan."""

    __tablename__ = "tenant_feature_grants"
    __table_args__ = (
        UniqueConstraint("tenant_id", "feature_id", name="uq_tenant_feature_grant"),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    feature_id: Mapped[UUID] = mapped_column(
        ForeignKey("feature_definitions.id", ondelete="RESTRICT"), index=True
    )
    status: Mapped[str] = mapped_column(String(20), default="DISABLED", index=True)
    configuration: Mapped[dict] = mapped_column(JSONB, default=dict)
    starts_at: Mapped[datetime | None] = mapped_column(nullable=True)
    ends_at: Mapped[datetime | None] = mapped_column(nullable=True)
    granted_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
