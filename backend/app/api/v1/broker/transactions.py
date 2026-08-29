"""
Financial Transactions API Endpoints
Handles deposit and withdrawal management
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func, and_
from typing import Literal

from app.db import get_db
from app.models.master import Transaction
from app.middleware.rbac_enforcer import require_permission
from app.middleware.audit_logger import AuditLogger
from app.security import get_current_user
from app.schemas import (
    TransactionCreate,
    TransactionStatusUpdate,
    TransactionResponse,
    PaginatedResponse,
)

router = APIRouter(prefix="/api/v1/broker/transactions", tags=["Transactions"])


@router.get("", response_model=PaginatedResponse[TransactionResponse])
async def list_transactions(
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    type: str = Query("ALL"),
    status: str = Query("ALL"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
    _=Depends(require_permission("deposits.view", "withdrawals.view")),
):
    """List transactions with filters"""
    query = select(Transaction).where(Transaction.broker_id == current_user.broker_id)

    if type != "ALL":
        query = query.where(Transaction.type == type)

    if status != "ALL":
        query = query.where(Transaction.status == status)

    # Get total
    count_query = select(func.count()).select_from(Transaction)
    count_query = count_query.where(query.whereclause)
    result = await db.execute(count_query)
    total = result.scalar()

    # Get paginated results
    query = query.order_by(desc(Transaction.created_at)).offset(offset).limit(limit)
    result = await db.execute(query)
    transactions = result.scalars().all()

    return {
        "items": [TransactionResponse.from_orm(t) for t in transactions],
        "total": total,
    }


@router.post("", response_model=TransactionResponse)
async def create_transaction(
    data: TransactionCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
    _=Depends(
        require_permission(
            "deposits.create",
            "withdrawals.create",
        )
    ),
):
    """Create new transaction (deposit/withdrawal)"""
    permission_key = f"{data.type.lower()}.create"

    transaction = Transaction(
        broker_id=current_user.broker_id,
        client_id=data.client_id,
        type=data.type,
        amount=data.amount,
        currency=data.currency,
        method=data.method,
        status="PENDING",
    )

    db.add(transaction)
    await db.flush()

    await AuditLogger.log_create(
        db,
        "Transaction",
        transaction.id,
        {
            "client": data.client_id,
            "type": data.type,
            "amount": str(data.amount),
            "method": data.method,
        },
    )

    await db.commit()
    return TransactionResponse.from_orm(transaction)


@router.get("/{transaction_id}", response_model=TransactionResponse)
async def get_transaction(
    transaction_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
    _=Depends(require_permission("deposits.view", "withdrawals.view")),
):
    """Get single transaction"""
    result = await db.execute(
        select(Transaction).where(
            and_(
                Transaction.id == transaction_id,
                Transaction.broker_id == current_user.broker_id,
            )
        )
    )
    transaction = result.scalar_one_or_none()

    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")

    return TransactionResponse.from_orm(transaction)


@router.put("/{transaction_id}/status")
async def update_transaction_status(
    transaction_id: str,
    data: TransactionStatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
    _=Depends(
        require_permission("deposits.approve", "withdrawals.approve")
    ),
):
    """Approve or reject transaction"""
    result = await db.execute(
        select(Transaction).where(
            and_(
                Transaction.id == transaction_id,
                Transaction.broker_id == current_user.broker_id,
            )
        )
    )
    transaction = result.scalar_one_or_none()

    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")

    if transaction.status != "PENDING":
        raise HTTPException(status_code=400, detail="Can only update pending transactions")

    old_status = transaction.status
    transaction.status = data.status

    if data.status == "APPROVED":
        transaction.status = "COMPLETED"

    await AuditLogger.log_update(
        db,
        "Transaction",
        transaction_id,
        {
            "status": old_status,
            "new_status": transaction.status,
            "action": "approval",
        },
    )

    await db.commit()

    return {
        "id": transaction.id,
        "status": transaction.status,
        "message": f"Transaction {data.status.lower()}",
    }
