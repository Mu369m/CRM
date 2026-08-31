"""
Client Lifecycle State Machine

Manages client status transitions through their journey:

NEW → REGISTERED → KYC_PENDING → VERIFIED → ACTIVE → DORMANT → SUSPENDED → CLOSED

State Meanings:
- NEW: Lead converted to client, initial state
- REGISTERED: Client account created, not yet verified
- KYC_PENDING: Waiting for KYC documents
- VERIFIED: KYC approved, ready to trade
- ACTIVE: Has activity (trading/deposits) recently
- DORMANT: No activity for extended period
- SUSPENDED: Account suspended by broker
- CLOSED: Account closed by client or broker

Rules:
- State transitions are unidirectional (mostly)
- Cannot delete client data when status changes
- Historical state changes are audited
- Each state transition may trigger automations
- Data remains queryable in all states

PRODUCTION RULE:
Status changes are informational.
Do NOT delete business data when status changes.
Preserve historical records.
"""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Client, AuditLog, Activity


class ClientStatus(StrEnum):
    """Client lifecycle states."""
    NEW = "NEW"
    REGISTERED = "REGISTERED"
    KYC_PENDING = "KYC_PENDING"
    VERIFIED = "VERIFIED"
    ACTIVE = "ACTIVE"
    DORMANT = "DORMANT"
    SUSPENDED = "SUSPENDED"
    CLOSED = "CLOSED"


class ClientLifecycleError(Exception):
    """Error during client state transition."""
    pass


# Valid state transitions
VALID_TRANSITIONS = {
    ClientStatus.NEW: [ClientStatus.REGISTERED, ClientStatus.CLOSED],
    ClientStatus.REGISTERED: [ClientStatus.KYC_PENDING, ClientStatus.CLOSED],
    ClientStatus.KYC_PENDING: [ClientStatus.VERIFIED, ClientStatus.REGISTERED, ClientStatus.CLOSED],
    ClientStatus.VERIFIED: [ClientStatus.ACTIVE, ClientStatus.SUSPENDED, ClientStatus.CLOSED],
    ClientStatus.ACTIVE: [ClientStatus.DORMANT, ClientStatus.SUSPENDED, ClientStatus.CLOSED],
    ClientStatus.DORMANT: [ClientStatus.ACTIVE, ClientStatus.SUSPENDED, ClientStatus.CLOSED],
    ClientStatus.SUSPENDED: [ClientStatus.ACTIVE, ClientStatus.CLOSED],
    ClientStatus.CLOSED: [],  # Terminal state
}


async def transition_client_status(
    db: AsyncSession,
    tenant_id: UUID,
    client_id: UUID,
    new_status: ClientStatus,
    actor_id: UUID,
    reason: str | None = None,
) -> Client:
    """
    Transition client to new status.
    
    Validates:
    1. Client exists
    2. Transition is valid
    3. No business data is deleted
    4. Audit trail is created
    5. Activity record is created
    6. Workflow automations are triggered (if configured)
    
    Returns: Updated Client
    """
    
    # Get client
    client = await db.execute(
        select(Client).where(
            and_(
                Client.id == client_id,
                Client.tenant_id == tenant_id,
            )
        )
    )
    client = client.scalar_one_or_none()
    
    if not client:
        raise ClientLifecycleError("Client not found")
    
    current_status = ClientStatus(client.status)
    
    # Validate transition
    if new_status not in VALID_TRANSITIONS.get(current_status, []):
        raise ClientLifecycleError(
            f"Invalid transition: {current_status} → {new_status}"
        )
    
    # Record old status
    old_status = client.status
    
    # Update status
    client.status = new_status.value
    client.updated_at = datetime.utcnow()
    
    # Create audit log
    audit_log = AuditLog(
        tenant_id=tenant_id,
        actor_id=actor_id,
        action="CLIENT_STATUS_CHANGED",
        metadata_json=str({
            "client_id": str(client_id),
            "old_status": old_status,
            "new_status": new_status.value,
            "reason": reason,
        }),
    )
    db.add(audit_log)
    
    # Create activity record (visible in client's timeline)
    activity = Activity(
        tenant_id=tenant_id,
        entity_type="CLIENT",
        entity_id=client_id,
        activity_type="STATUS_CHANGE",
        description=f"Status changed: {old_status} → {new_status.value}",
        user_id=actor_id,
        metadata_json={
            "old_status": old_status,
            "new_status": new_status.value,
            "reason": reason,
        },
    )
    db.add(activity)
    
    await db.commit()
    
    # Trigger automations (e.g., send notification, create task)
    # This would be handled by workflow engine
    
    return client


async def register_client(
    db: AsyncSession,
    tenant_id: UUID,
    client_id: UUID,
    actor_id: UUID,
) -> Client:
    """
    Transition NEW → REGISTERED.
    
    When client completes registration form.
    """
    return await transition_client_status(
        db,
        tenant_id,
        client_id,
        ClientStatus.REGISTERED,
        actor_id,
        reason="Client registration completed",
    )


async def request_kyc(
    db: AsyncSession,
    tenant_id: UUID,
    client_id: UUID,
    actor_id: UUID,
) -> Client:
    """
    Transition REGISTERED → KYC_PENDING.
    
    When broker requests KYC documents.
    """
    return await transition_client_status(
        db,
        tenant_id,
        client_id,
        ClientStatus.KYC_PENDING,
        actor_id,
        reason="KYC documentation requested",
    )


async def approve_kyc(
    db: AsyncSession,
    tenant_id: UUID,
    client_id: UUID,
    actor_id: UUID,
) -> Client:
    """
    Transition KYC_PENDING → VERIFIED.
    
    When compliance approves KYC.
    """
    return await transition_client_status(
        db,
        tenant_id,
        client_id,
        ClientStatus.VERIFIED,
        actor_id,
        reason="KYC approval granted",
    )


async def mark_active(
    db: AsyncSession,
    tenant_id: UUID,
    client_id: UUID,
    actor_id: UUID,
) -> Client:
    """
    Transition VERIFIED → ACTIVE.
    
    When client makes first deposit or trade.
    Can be automated by system.
    """
    return await transition_client_status(
        db,
        tenant_id,
        client_id,
        ClientStatus.ACTIVE,
        actor_id,
        reason="Client became active (first activity)",
    )


async def mark_dormant(
    db: AsyncSession,
    tenant_id: UUID,
    client_id: UUID,
    actor_id: UUID,
    days_inactive: int = 90,
) -> Client:
    """
    Transition ACTIVE → DORMANT.
    
    When no activity for extended period (e.g., 90 days).
    Typically automated by system.
    """
    return await transition_client_status(
        db,
        tenant_id,
        client_id,
        ClientStatus.DORMANT,
        actor_id,
        reason=f"No activity for {days_inactive} days",
    )


async def suspend_client(
    db: AsyncSession,
    tenant_id: UUID,
    client_id: UUID,
    actor_id: UUID,
    reason: str,
) -> Client:
    """
    Transition to SUSPENDED.
    
    Broker can suspend client for compliance reasons.
    Can be from VERIFIED, ACTIVE, or DORMANT.
    Data is preserved.
    """
    # Get current status
    client = await db.execute(
        select(Client).where(
            and_(
                Client.id == client_id,
                Client.tenant_id == tenant_id,
            )
        )
    )
    client = client.scalar_one_or_none()
    
    if not client:
        raise ClientLifecycleError("Client not found")
    
    # Can suspend from active states
    current_status = ClientStatus(client.status)
    if current_status not in [ClientStatus.VERIFIED, ClientStatus.ACTIVE, ClientStatus.DORMANT]:
        raise ClientLifecycleError(
            f"Cannot suspend client in {current_status} status"
        )
    
    return await transition_client_status(
        db,
        tenant_id,
        client_id,
        ClientStatus.SUSPENDED,
        actor_id,
        reason=f"Suspended: {reason}",
    )


async def close_client(
    db: AsyncSession,
    tenant_id: UUID,
    client_id: UUID,
    actor_id: UUID,
    reason: str,
) -> Client:
    """
    Transition to CLOSED (terminal state).
    
    Account closure (client or broker initiated).
    All data is preserved.
    Account cannot be reopened (create new account instead).
    """
    return await transition_client_status(
        db,
        tenant_id,
        client_id,
        ClientStatus.CLOSED,
        actor_id,
        reason=f"Closed: {reason}",
    )


async def get_client_status_history(
    db: AsyncSession,
    tenant_id: UUID,
    client_id: UUID,
) -> list[dict]:
    """
    Get client's complete status change history.
    
    Returns list of all status transitions with timestamps.
    """
    
    # Query audit logs for this client
    audit_logs = await db.execute(
        select(AuditLog).where(
            and_(
                AuditLog.tenant_id == tenant_id,
                AuditLog.action == "CLIENT_STATUS_CHANGED",
                # Would also filter by entity_id if stored separately
            )
        )
    )
    
    logs = audit_logs.scalars().all()
    
    history = []
    for log in logs:
        import json
        metadata = json.loads(log.metadata_json) if log.metadata_json else {}
        if metadata.get("client_id") == str(client_id):
            history.append({
                "timestamp": log.created_at,
                "old_status": metadata.get("old_status"),
                "new_status": metadata.get("new_status"),
                "reason": metadata.get("reason"),
                "changed_by": log.actor_id,
            })
    
    # Sort by timestamp
    history.sort(key=lambda x: x["timestamp"], reverse=False)
    
    return history


__all__ = [
    "ClientStatus",
    "ClientLifecycleError",
    "VALID_TRANSITIONS",
    "transition_client_status",
    "register_client",
    "request_kyc",
    "approve_kyc",
    "mark_active",
    "mark_dormant",
    "suspend_client",
    "close_client",
    "get_client_status_history",
]
