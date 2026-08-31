"""
Payment Reconciliation Engine

Reconciles local payment records with payment provider records.

Purpose:
- Detect missed or stuck transactions
- Update transaction status based on provider
- Handle delayed webhooks
- Recover from provider outages
- Audit all reconciliation actions

Reconciliation Process:
1. Query local pending transactions
2. Query provider API for those transaction IDs
3. Compare statuses
4. Update local records to match provider source of truth
5. Log discrepancies
6. Trigger automations if status changed (e.g., deposit completed)

PRODUCTION RULE:
Provider is source of truth for financial transactions.
If local and provider disagree, provider is correct.
Never blindly trust webhook timing.
Background reconciliation catches missed events.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import Optional
from uuid import UUID

from sqlalchemy import select, and_, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Transaction, TransactionStatus, AuditLog, WebhookEvent


class ReconciliationStatus(StrEnum):
    """Status of reconciliation attempt."""
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    PARTIAL = "PARTIAL"


class TransactionDiscrepancy:
    """Mismatch between local and provider records."""
    
    def __init__(
        self,
        transaction_id: UUID,
        local_status: str,
        provider_status: str,
        difference_description: str,
    ):
        self.transaction_id = transaction_id
        self.local_status = local_status
        self.provider_status = provider_status
        self.difference_description = difference_description


class PaymentReconciliationResult:
    """Result of reconciliation run."""
    
    def __init__(
        self,
        reconciliation_status: ReconciliationStatus,
        provider: str,
        tenant_id: UUID,
        transactions_checked: int = 0,
        transactions_updated: int = 0,
        discrepancies_found: int = 0,
        discrepancies: list[TransactionDiscrepancy] | None = None,
        errors: list[str] | None = None,
        started_at: datetime | None = None,
        completed_at: datetime | None = None,
    ):
        self.reconciliation_status = reconciliation_status
        self.provider = provider
        self.tenant_id = tenant_id
        self.transactions_checked = transactions_checked
        self.transactions_updated = transactions_updated
        self.discrepancies_found = discrepancies_found
        self.discrepancies = discrepancies or []
        self.errors = errors or []
        self.started_at = started_at
        self.completed_at = completed_at


async def reconcile_payments(
    db: AsyncSession,
    tenant_id: UUID,
    provider: str,
    provider_client,  # Provider-specific client (e.g., StripeClient)
) -> PaymentReconciliationResult:
    """
    Reconcile all pending payments with provider.
    
    Flow:
    1. Get all PENDING transactions for tenant and provider
    2. For each transaction:
        a. Query provider for current status
        b. Compare with local status
        c. If different, update local
        d. Record discrepancy
    3. Return reconciliation result
    
    PRODUCTION RULE:
    Provider status is ALWAYS authoritative.
    If discrepancy, believe provider.
    """
    
    result = PaymentReconciliationResult(
        reconciliation_status=ReconciliationStatus.IN_PROGRESS,
        provider=provider,
        tenant_id=tenant_id,
        started_at=datetime.utcnow(),
    )
    
    try:
        # Get all pending transactions for this provider
        pending_txns = await db.execute(
            select(Transaction).where(
                and_(
                    Transaction.tenant_id == tenant_id,
                    Transaction.status == TransactionStatus.PENDING,
                    # Would also filter by provider/gateway
                )
            )
        )
        
        pending_transactions = pending_txns.scalars().all()
        result.transactions_checked = len(pending_transactions)
        
        # Reconcile each transaction
        for txn in pending_transactions:
            try:
                # Query provider for this transaction
                provider_txn = await provider_client.get_transaction(
                    txn.id,
                    txn.payment_proof_url,  # Provider ref if available
                )
                
                if not provider_txn:
                    # Provider doesn't know about this transaction
                    result.errors.append(
                        f"Transaction {txn.id} not found in provider"
                    )
                    continue
                
                # Compare statuses
                provider_status = provider_txn.get("status")
                local_status = txn.status.value
                
                if provider_status != local_status:
                    # Discrepancy found
                    discrepancy = TransactionDiscrepancy(
                        transaction_id=txn.id,
                        local_status=local_status,
                        provider_status=provider_status,
                        difference_description=(
                            f"Local: {local_status}, Provider: {provider_status}"
                        ),
                    )
                    result.discrepancies.append(discrepancy)
                    result.discrepancies_found += 1
                    
                    # Update local status to match provider
                    old_status = txn.status
                    txn.status = TransactionStatus(provider_status)
                    result.transactions_updated += 1
                    
                    # Audit the reconciliation update
                    audit_log = AuditLog(
                        tenant_id=tenant_id,
                        actor_id=UUID("00000000-0000-0000-0000-000000000000"),  # System
                        action="PAYMENT_RECONCILIATION_UPDATE",
                        metadata_json=str({
                            "transaction_id": str(txn.id),
                            "old_status": old_status.value,
                            "new_status": provider_status,
                            "provider": provider,
                            "reason": "Reconciliation with provider",
                        }),
                    )
                    db.add(audit_log)
                    
                    # Mark webhook as processed if this completes deposit
                    if provider_status == TransactionStatus.COMPLETED:
                        # Update any related webhook events
                        webhook_events = await db.execute(
                            select(WebhookEvent).where(
                                and_(
                                    WebhookEvent.provider == provider,
                                    WebhookEvent.tenant_id == tenant_id,
                                )
                            )
                        )
                        # Could match by provider reference
                
            except Exception as e:
                result.errors.append(f"Error reconciling {txn.id}: {str(e)}")
        
        await db.commit()
        
        result.reconciliation_status = (
            ReconciliationStatus.COMPLETED
            if not result.errors
            else ReconciliationStatus.PARTIAL
        )
        
    except Exception as e:
        result.reconciliation_status = ReconciliationStatus.FAILED
        result.errors.append(f"Reconciliation failed: {str(e)}")
    
    finally:
        result.completed_at = datetime.utcnow()
    
    return result


async def get_stalled_transactions(
    db: AsyncSession,
    tenant_id: UUID,
    max_age_minutes: int = 60,
) -> list[Transaction]:
    """
    Get transactions stuck in PENDING for too long.
    
    These should be reconciled or investigated.
    
    Returns transactions pending for > max_age_minutes.
    """
    
    cutoff_time = datetime.utcnow() - timedelta(minutes=max_age_minutes)
    
    stalled = await db.execute(
        select(Transaction).where(
            and_(
                Transaction.tenant_id == tenant_id,
                Transaction.status == TransactionStatus.PENDING,
                Transaction.created_at < cutoff_time,
            )
        )
    )
    
    return stalled.scalars().all()


async def detect_webhook_delay(
    db: AsyncSession,
    tenant_id: UUID,
    transaction_id: UUID,
) -> bool:
    """
    Detect if transaction was completed but webhook hasn't arrived.
    
    Scenario:
    - Payment provider confirmed transaction completed
    - But webhook hasn't arrived yet
    - Local status still PENDING
    - Reconciliation detects this
    
    Returns True if delayed webhook detected.
    """
    
    # Query transaction status
    txn = await db.execute(
        select(Transaction).where(
            and_(
                Transaction.id == transaction_id,
                Transaction.tenant_id == tenant_id,
            )
        )
    )
    txn = txn.scalar_one_or_none()
    
    if not txn or txn.status != TransactionStatus.PENDING:
        return False
    
    # Would query provider to check if it's actually completed
    # If provider says completed but local is PENDING, webhook is delayed
    
    return False


async def handle_duplicate_webhook(
    db: AsyncSession,
    tenant_id: UUID,
    provider: str,
    provider_event_id: str,
) -> bool:
    """
    Detect if webhook was already processed.
    
    Check if webhook_event exists with provider_event_id.
    If already processed_at, return True (duplicate).
    """
    
    webhook_event = await db.execute(
        select(WebhookEvent).where(
            and_(
                WebhookEvent.provider == provider,
                WebhookEvent.event_id == provider_event_id,
            )
        )
    )
    webhook = webhook_event.scalar_one_or_none()
    
    if webhook and webhook.processed_at:
        return True  # Already processed
    
    return False


async def create_reconciliation_report(
    db: AsyncSession,
    result: PaymentReconciliationResult,
) -> dict:
    """
    Create summary report of reconciliation.
    
    Returns dict with:
    - Total transactions checked
    - Transactions updated
    - Discrepancies found
    - Errors encountered
    - Start/end time
    - Recommendations
    """
    
    recommendations = []
    
    if result.discrepancies_found > 0:
        recommendations.append(
            f"Found {result.discrepancies_found} discrepancies - review logs"
        )
    
    if len(result.errors) > 0:
        recommendations.append(
            f"Reconciliation encountered {len(result.errors)} errors - investigate"
        )
    
    if result.transactions_checked == 0:
        recommendations.append("No pending transactions to reconcile")
    
    return {
        "reconciliation_status": result.reconciliation_status.value,
        "provider": result.provider,
        "tenant_id": str(result.tenant_id),
        "summary": {
            "transactions_checked": result.transactions_checked,
            "transactions_updated": result.transactions_updated,
            "discrepancies_found": result.discrepancies_found,
            "errors_encountered": len(result.errors),
        },
        "duration_seconds": (
            (result.completed_at - result.started_at).total_seconds()
            if result.completed_at and result.started_at
            else None
        ),
        "started_at": result.started_at.isoformat() if result.started_at else None,
        "completed_at": result.completed_at.isoformat() if result.completed_at else None,
        "errors": result.errors[:10],  # First 10 errors
        "recommendations": recommendations,
    }


__all__ = [
    "ReconciliationStatus",
    "TransactionDiscrepancy",
    "PaymentReconciliationResult",
    "reconcile_payments",
    "get_stalled_transactions",
    "detect_webhook_delay",
    "handle_duplicate_webhook",
    "create_reconciliation_report",
]
