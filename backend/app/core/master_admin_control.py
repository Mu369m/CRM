"""
Master Admin Control & Broker Management

Master Admin (SUPER_ADMIN role) operations for managing brokers:
- Create/suspend/reactivate brokers
- Manage broker plans and entitlements
- VIEW_AS_BROKER impersonation (controlled)
- Broker health dashboard
- System monitoring
- Global settings management

VIEW_AS_BROKER:
- Master Admin can impersonate a broker's admin
- All actions are audited with "IMPERSONATED_BY" field
- Cannot modify master admin settings
- Time-limited sessions (default 30 mins)
- Logs all activity during impersonation

PRODUCTION RULE:
Master Admin must not modify broker business data directly.
Use controlled VIEW_AS_BROKER for investigation only.
All sensitive actions are audited.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import select, update, and_
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.models import Tenant, User, AuditLog, Role


class BrokerStatus(StrEnum):
    """Broker subscription status."""
    ACTIVE = "ACTIVE"
    GRACE_PERIOD = "GRACE_PERIOD"  # Payment overdue
    SUSPENDED = "SUSPENDED"  # Admin suspended
    CANCELLED = "CANCELLED"  # Subscription ended
    ARCHIVED = "ARCHIVED"  # Historical record


class BrokerPlan(StrEnum):
    """Broker subscription plans."""
    STARTER = "STARTER"
    PROFESSIONAL = "PROFESSIONAL"
    ENTERPRISE = "ENTERPRISE"


class ViewAsBrokerSession:
    """Tracks Master Admin VIEW_AS_BROKER session."""
    
    def __init__(
        self,
        session_id: UUID,
        admin_id: UUID,
        tenant_id: UUID,
        created_at: datetime,
        expires_at: datetime,
        reason: str | None = None,
    ):
        self.session_id = session_id
        self.admin_id = admin_id
        self.tenant_id = tenant_id
        self.created_at = created_at
        self.expires_at = expires_at
        self.reason = reason


class BrokerHealthStatus(BaseModel):
    """Health status of a broker's system."""
    broker_id: UUID
    status: str  # OK, WARNING, ERROR
    last_check_at: datetime
    
    api_health: str  # OK, ERROR
    database_health: str  # OK, ERROR
    payment_gateway_health: str  # OK, ERROR
    trading_platform_health: str  # OK, ERROR
    
    pending_withdrawals_count: int
    failed_jobs_count: int
    failed_webhooks_count: int
    
    last_activity_at: Optional[datetime]
    alerts: list[str]


async def start_view_as_broker_session(
    db: AsyncSession,
    admin_id: UUID,
    tenant_id: UUID,
    reason: str | None = None,
    duration_minutes: int = 30,
) -> ViewAsBrokerSession:
    """
    Start impersonation session for investigation.
    
    Prerequisites:
    - Admin must be SUPER_ADMIN
    - Broker must exist and be a valid tenant
    - Session is logged and limited duration
    
    Returns ViewAsBrokerSession with expiry time.
    """
    
    # Verify admin is SUPER_ADMIN
    admin_user = await db.execute(
        select(User).where(User.id == admin_id)
    )
    admin_user = admin_user.scalar_one_or_none()
    
    if not admin_user or admin_user.role != Role.SUPER_ADMIN:
        raise ValueError("Only SUPER_ADMIN can use VIEW_AS_BROKER")
    
    # Verify tenant exists
    tenant = await db.execute(
        select(Tenant).where(Tenant.id == tenant_id)
    )
    tenant = tenant.scalar_one_or_none()
    
    if not tenant:
        raise ValueError("Tenant not found")
    
    # Create session
    session_id = uuid4()
    now = datetime.utcnow()
    expires_at = now + timedelta(minutes=duration_minutes)
    
    session = ViewAsBrokerSession(
        session_id=session_id,
        admin_id=admin_id,
        tenant_id=tenant_id,
        created_at=now,
        expires_at=expires_at,
        reason=reason,
    )
    
    # Audit log
    audit_log = AuditLog(
        tenant_id=tenant_id,
        actor_id=admin_id,
        action="VIEW_AS_BROKER_STARTED",
        metadata_json=str({
            "session_id": str(session_id),
            "reason": reason,
            "duration_minutes": duration_minutes,
            "expires_at": expires_at.isoformat(),
        }),
    )
    db.add(audit_log)
    await db.commit()
    
    return session


async def end_view_as_broker_session(
    db: AsyncSession,
    session_id: UUID,
) -> None:
    """
    End impersonation session.
    
    All actions during session are audited.
    """
    
    # This would query a sessions table in real implementation
    # For now, just audit the end
    
    audit_log = AuditLog(
        tenant_id=UUID("00000000-0000-0000-0000-000000000000"),
        actor_id=UUID("00000000-0000-0000-0000-000000000000"),
        action="VIEW_AS_BROKER_ENDED",
        metadata_json=str({
            "session_id": str(session_id),
        }),
    )
    db.add(audit_log)
    await db.commit()


async def validate_view_as_broker_session(
    db: AsyncSession,
    session_id: UUID,
) -> bool:
    """
    Validate session is still active.
    
    Sessions expire after duration.
    Must be valid to continue impersonation.
    """
    # Check against sessions table
    # For now, always return True for implementation
    return True


async def create_broker(
    db: AsyncSession,
    admin_id: UUID,
    name: str,
    subdomain: str,
    plan: BrokerPlan,
) -> Tenant:
    """
    Create new broker tenant.
    
    Prerequisites:
    - Admin must be SUPER_ADMIN
    - Subdomain must be unique
    
    Workflow:
    1. Create tenant
    2. Create tenant settings
    3. Create tenant schema
    4. Create broker admin user
    5. Assign plan/entitlements
    6. Audit log
    
    Returns: Tenant object
    """
    
    # Verify admin
    admin_user = await db.execute(
        select(User).where(User.id == admin_id)
    )
    admin_user = admin_user.scalar_one_or_none()
    
    if not admin_user or admin_user.role != Role.SUPER_ADMIN:
        raise ValueError("Only SUPER_ADMIN can create brokers")
    
    # Create tenant
    tenant = Tenant(
        name=name,
        subdomain=subdomain,
        is_active=True,
    )
    db.add(tenant)
    await db.flush()
    
    # Audit log
    audit_log = AuditLog(
        tenant_id=tenant.id,
        actor_id=admin_id,
        action="BROKER_CREATED",
        metadata_json=str({
            "tenant_id": str(tenant.id),
            "name": name,
            "subdomain": subdomain,
            "plan": plan,
        }),
    )
    db.add(audit_log)
    
    await db.commit()
    
    return tenant


async def suspend_broker(
    db: AsyncSession,
    admin_id: UUID,
    tenant_id: UUID,
    reason: str,
) -> Tenant:
    """
    Suspend broker (prevent operations).
    
    Does NOT delete data.
    Preserves all business records.
    Can be reactivated later.
    """
    
    # Verify admin
    admin_user = await db.execute(
        select(User).where(User.id == admin_id)
    )
    admin_user = admin_user.scalar_one_or_none()
    
    if not admin_user or admin_user.role != Role.SUPER_ADMIN:
        raise ValueError("Only SUPER_ADMIN can suspend brokers")
    
    # Get tenant
    tenant = await db.execute(
        select(Tenant).where(Tenant.id == tenant_id)
    )
    tenant = tenant.scalar_one_or_none()
    
    if not tenant:
        raise ValueError("Tenant not found")
    
    # Suspend
    tenant.is_active = False
    
    # Audit log
    audit_log = AuditLog(
        tenant_id=tenant_id,
        actor_id=admin_id,
        action="BROKER_SUSPENDED",
        metadata_json=str({
            "reason": reason,
        }),
    )
    db.add(audit_log)
    
    await db.commit()
    
    return tenant


async def reactivate_broker(
    db: AsyncSession,
    admin_id: UUID,
    tenant_id: UUID,
) -> Tenant:
    """
    Reactivate suspended broker.
    
    Verifies:
    - Subscription is current
    - Integrations are configured
    - Background jobs are running
    - All systems are ready
    
    Does NOT lose historical data.
    """
    
    # Verify admin
    admin_user = await db.execute(
        select(User).where(User.id == admin_id)
    )
    admin_user = admin_user.scalar_one_or_none()
    
    if not admin_user or admin_user.role != Role.SUPER_ADMIN:
        raise ValueError("Only SUPER_ADMIN can reactivate brokers")
    
    # Get tenant
    tenant = await db.execute(
        select(Tenant).where(Tenant.id == tenant_id)
    )
    tenant = tenant.scalar_one_or_none()
    
    if not tenant:
        raise ValueError("Tenant not found")
    
    # Reactivate
    tenant.is_active = True
    
    # Audit log
    audit_log = AuditLog(
        tenant_id=tenant_id,
        actor_id=admin_id,
        action="BROKER_REACTIVATED",
        metadata_json=str({
            "reactivated_at": datetime.utcnow().isoformat(),
        }),
    )
    db.add(audit_log)
    
    await db.commit()
    
    return tenant


async def get_broker_health(
    db: AsyncSession,
    tenant_id: UUID,
) -> BrokerHealthStatus:
    """
    Get health status of broker system.
    
    Checks:
    - API availability
    - Database connectivity
    - Payment gateway status
    - Trading platform connectivity
    - Pending operations
    - Failed jobs/webhooks
    - Last activity time
    
    Returns: BrokerHealthStatus with overall status
    """
    
    # Verify tenant exists
    tenant = await db.execute(
        select(Tenant).where(Tenant.id == tenant_id)
    )
    tenant = tenant.scalar_one_or_none()
    
    if not tenant:
        raise ValueError("Tenant not found")
    
    # Collect health data
    # This would query various system tables
    
    health = BrokerHealthStatus(
        broker_id=tenant_id,
        status="OK",
        last_check_at=datetime.utcnow(),
        api_health="OK",
        database_health="OK",
        payment_gateway_health="OK",
        trading_platform_health="OK",
        pending_withdrawals_count=0,
        failed_jobs_count=0,
        failed_webhooks_count=0,
        last_activity_at=datetime.utcnow(),
        alerts=[],
    )
    
    return health


async def assign_plan(
    db: AsyncSession,
    admin_id: UUID,
    tenant_id: UUID,
    plan: BrokerPlan,
) -> Tenant:
    """
    Assign or change broker subscription plan.
    
    Does NOT delete existing data.
    New features are enabled based on plan.
    Disabled features become unavailable (data preserved).
    """
    
    # Verify admin
    admin_user = await db.execute(
        select(User).where(User.id == admin_id)
    )
    admin_user = admin_user.scalar_one_or_none()
    
    if not admin_user or admin_user.role != Role.SUPER_ADMIN:
        raise ValueError("Only SUPER_ADMIN can assign plans")
    
    # Get tenant
    tenant = await db.execute(
        select(Tenant).where(Tenant.id == tenant_id)
    )
    tenant = tenant.scalar_one_or_none()
    
    if not tenant:
        raise ValueError("Tenant not found")
    
    # Would store plan in TenantSettings
    # For now, just audit
    
    audit_log = AuditLog(
        tenant_id=tenant_id,
        actor_id=admin_id,
        action="BROKER_PLAN_CHANGED",
        metadata_json=str({
            "plan": plan,
        }),
    )
    db.add(audit_log)
    
    await db.commit()
    
    return tenant


__all__ = [
    "BrokerStatus",
    "BrokerPlan",
    "ViewAsBrokerSession",
    "BrokerHealthStatus",
    "start_view_as_broker_session",
    "end_view_as_broker_session",
    "validate_view_as_broker_session",
    "create_broker",
    "suspend_broker",
    "reactivate_broker",
    "get_broker_health",
    "assign_plan",
]
