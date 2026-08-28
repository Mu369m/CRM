"""SaaS-owner master database models for BYODB tenant routing."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class MasterBase(DeclarativeBase):
    """Metadata that must exist only in the SaaS owner's master database."""


class BrokerTenant(MasterBase):
    """Minimal broker registry; client financial data belongs in the private DB."""

    __tablename__ = "broker_tenants"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    company_name: Mapped[str] = mapped_column(String(160))
    subdomain: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    custom_domain: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    encrypted_db_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    subscription_status: Mapped[str] = mapped_column(String(30), default="TRIAL")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class SystemBroadcast(MasterBase):
    """Global banner configuration stored in the SaaS master database."""

    __tablename__ = "system_broadcasts"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    broadcast_type: Mapped[str] = mapped_column(String(20))
    message: Mapped[str] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    target_brokers: Mapped[str] = mapped_column(String(30), default="ALL_BROKERS")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
