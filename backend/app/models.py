"""Core brokerage CRM persistence models."""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, JSON, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Declarative metadata shared by Alembic and the application."""


class Role(StrEnum):
    SUPER_ADMIN = "SUPER_ADMIN"
    COMPLIANCE = "COMPLIANCE"
    FINANCE = "FINANCE"
    SALES = "SALES"
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
    ADJUSTMENT = "ADJUSTMENT"


class RequestStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"


class AccountPlatform(StrEnum):
    MT4 = "MT4"
    MT5 = "MT5"
    CTRADER = "CTRADER"


class RebateStrategy(StrEnum):
    PER_LOT_FIXED = "PER_LOT_FIXED"
    PERCENTAGE_SPREAD = "PERCENTAGE_SPREAD"
    ASSET_BASED = "ASSET_BASED"


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(160))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    users: Mapped[list["User"]] = relationship(back_populates="tenant")
    wallets: Mapped[list["Wallet"]] = relationship(back_populates="tenant")
    settings: Mapped["TenantSettings | None"] = relationship(back_populates="tenant", uselist=False)


class User(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(default=Role.TRADER)
    kyc_status: Mapped[KycStatus] = mapped_column(default=KycStatus.PENDING)
    totp_secret_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    totp_enabled: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    tenant: Mapped[Tenant] = relationship(back_populates="users")
    wallet: Mapped["Wallet | None"] = relationship(back_populates="owner", uselist=False)


class Wallet(Base):
    __tablename__ = "wallets"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    balance: Mapped[Decimal] = mapped_column(Numeric(20, 8), default=Decimal("0"))
    tenant: Mapped[Tenant] = relationship(back_populates="wallets")
    owner: Mapped[User] = relationship(back_populates="wallet")
    entries: Mapped[list["LedgerEntry"]] = relationship(back_populates="wallet")


class LedgerEntry(Base):
    __tablename__ = "ledger_entries"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    wallet_id: Mapped[UUID] = mapped_column(ForeignKey("wallets.id", ondelete="RESTRICT"), index=True)
    entry_type: Mapped[LedgerEntryType] = mapped_column()
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    reference: Mapped[str] = mapped_column(String(120), unique=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    wallet: Mapped[Wallet] = relationship(back_populates="entries")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    actor_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True))
    action: Mapped[str] = mapped_column(String(120))
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class WebhookEvent(Base):
    __tablename__ = "webhook_events"
    __table_args__ = (UniqueConstraint("provider", "event_id", name="uq_webhook_provider_event"),)

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID | None] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True)
    provider: Mapped[str] = mapped_column(String(80))
    event_id: Mapped[str] = mapped_column(String(180))
    payload: Mapped[dict] = mapped_column(JSON)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class KycDocument(Base):
    __tablename__ = "kyc_documents"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    document_type: Mapped[str] = mapped_column(String(50))
    storage_key: Mapped[str] = mapped_column(Text)
    status: Mapped[KycStatus] = mapped_column(default=KycStatus.PENDING)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class TradingAccount(Base):
    __tablename__ = "trading_accounts"
    __table_args__ = (UniqueConstraint("platform", "external_login", "server", name="uq_trading_account_external"),)

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    platform: Mapped[AccountPlatform] = mapped_column()
    external_login: Mapped[str] = mapped_column(String(80))
    server: Mapped[str] = mapped_column(String(160))
    is_demo: Mapped[bool] = mapped_column(default=False)
    leverage: Mapped[int] = mapped_column(default=100)
    is_locked: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MoneyRequest(Base):
    __tablename__ = "money_requests"
    __table_args__ = (UniqueConstraint("idempotency_key", name="uq_money_request_idempotency"),)

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(20))
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    currency: Mapped[str] = mapped_column(String(3))
    status: Mapped[RequestStatus] = mapped_column(default=RequestStatus.PENDING)
    provider_reference: Mapped[str | None] = mapped_column(String(160), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(120), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class IbPartner(Base):
    __tablename__ = "ib_partners"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    parent_id: Mapped[UUID | None] = mapped_column(ForeignKey("ib_partners.id"), nullable=True, index=True)
    referral_code: Mapped[str] = mapped_column(String(50), unique=True)
    commission_rate: Mapped[Decimal] = mapped_column(Numeric(12, 6), default=Decimal("0"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TenantSettings(Base):
    __tablename__ = "tenant_settings"

    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), primary_key=True)
    primary_color: Mapped[str] = mapped_column(String(20), default="#45b69c")
    secondary_color: Mapped[str] = mapped_column(String(20), default="#1d3430")
    logo_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    favicon_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta_title: Mapped[str] = mapped_column(String(160), default="Brokerage CRM")
    support_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    max_ib_levels: Mapped[int] = mapped_column(default=5)
    tenant_schema: Mapped[str] = mapped_column(String(80), unique=True)
    tenant: Mapped[Tenant] = relationship(back_populates="settings")


class RebateRule(Base):
    __tablename__ = "rebate_rules"
    __table_args__ = (UniqueConstraint("tenant_id", "instrument_group", "level", name="uq_rebate_rule_scope"),)

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    instrument_group: Mapped[str] = mapped_column(String(80))
    strategy: Mapped[RebateStrategy] = mapped_column()
    level: Mapped[int] = mapped_column()
    fixed_per_lot: Mapped[Decimal] = mapped_column(Numeric(20, 8), default=Decimal("0"))
    spread_percentage: Mapped[Decimal] = mapped_column(Numeric(12, 8), default=Decimal("0"))
    asset_class: Mapped[str | None] = mapped_column(String(30), nullable=True)
    enabled: Mapped[bool] = mapped_column(default=True)


class KycRequirement(Base):
    __tablename__ = "kyc_requirements"
    __table_args__ = (UniqueConstraint("tenant_id", "document_type", name="uq_kyc_requirement_type"),)

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    document_type: Mapped[str] = mapped_column(String(50))
    required: Mapped[bool] = mapped_column(default=True)
    applies_to_country: Mapped[str | None] = mapped_column(String(2), nullable=True)
    enabled: Mapped[bool] = mapped_column(default=True)


class BonusRule(Base):
    __tablename__ = "bonus_rules"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    deposit_percentage: Mapped[Decimal] = mapped_column(Numeric(12, 8), default=Decimal("0"))
    max_credit: Mapped[Decimal] = mapped_column(Numeric(20, 8), default=Decimal("0"))
    withdrawal_lot_target: Mapped[Decimal] = mapped_column(Numeric(20, 8), default=Decimal("0"))
    enabled: Mapped[bool] = mapped_column(default=True)


class ManagerConnection(Base):
    __tablename__ = "manager_connections"
    __table_args__ = (UniqueConstraint("tenant_id", "name", name="uq_manager_connection_name"),)

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    platform: Mapped[AccountPlatform] = mapped_column()
    name: Mapped[str] = mapped_column(String(100))
    server: Mapped[str] = mapped_column(String(160))
    login: Mapped[str] = mapped_column(String(100))
    encrypted_password: Mapped[str] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
