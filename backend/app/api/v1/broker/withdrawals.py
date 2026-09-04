"""
Withdrawal management API endpoints.

Handles client withdrawal processing, approval workflows, and financial tracking.
"""

from uuid import UUID
from datetime import datetime
from typing import Optional, List
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from app.core.db_router import get_tenant_db
from app.security import current_claims
from app.models import (
    Withdrawal,
    WithdrawalMethod,
    Client,
    Activity,
    ClientFinancials,
)
from app.middleware.permission_check import check_permission

router = APIRouter(prefix="/api/v1/broker/withdrawals", tags=["Withdrawals"])


# ========== Schemas ==========


class WithdrawalMethodCreate(BaseModel):
    name: str = Field(..., max_length=200)
    provider: str = Field(..., max_length=100)
    method_type: str = Field(..., description="CARD, BANK, CRYPTO, E-WALLET")
    min_amount: Optional[Decimal] = None
    max_amount: Optional[Decimal] = None
    processing_fee_percent: Decimal = Field(default=Decimal("0"), decimal_places=2)
    processing_time_hours: Optional[int] = None

    class Config:
        json_schema_extra = {
            "example": {
                "name": "Bank Wire",
                "provider": "Internal",
                "method_type": "BANK",
                "processing_fee_percent": Decimal("1.5"),
                "processing_time_hours": 24,
            }
        }


class WithdrawalCreate(BaseModel):
    client_id: UUID
    amount: Decimal = Field(..., gt=0)
    currency: str = Field(..., min_length=3, max_length=3)
    method_id: UUID
    payment_reference: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "client_id": "550e8400-e29b-41d4-a716-446655440000",
                "amount": Decimal("500.00"),
                "currency": "USD",
                "method_id": "550e8400-e29b-41d4-a716-446655440001",
            }
        }


class WithdrawalApprove(BaseModel):
    approved_at: Optional[datetime] = None


class WithdrawalReject(BaseModel):
    rejection_reason: str = Field(..., max_length=500)


class WithdrawalMethodResponse(BaseModel):
    id: UUID
    name: str
    provider: str
    method_type: str
    min_amount: Optional[float]
    max_amount: Optional[float]
    processing_fee_percent: float
    processing_time_hours: Optional[int]
    is_active: bool

    class Config:
        from_attributes = True


class WithdrawalResponse(BaseModel):
    id: UUID
    client_id: UUID
    amount: float
    currency: str
    method_name: str
    status: str
    processing_fee: float
    net_amount: float
    approved_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class WithdrawalDetailResponse(WithdrawalResponse):
    payment_reference: Optional[str]
    rejection_reason: Optional[str]
    approved_by: Optional[UUID]
    rejected_by: Optional[UUID]


class WithdrawalListResponse(BaseModel):
    total: int
    page: int
    limit: int
    items: List[WithdrawalResponse]


def _available_client_balance(client: Client) -> Decimal:
    """Treat an uninitialized client balance as zero."""
    return client.net_deposits or Decimal("0")


# ========== Withdrawal Method Management ==========


@router.post(
    "/methods",
    response_model=WithdrawalMethodResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_withdrawal_method(
    payload: WithdrawalMethodCreate,
    claims: dict = Depends(current_claims),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Create withdrawal payment method. Requires: settings.manage"""

    tenant_id = UUID(claims["tenant_id"])

    # Check permission
    has_permission = await check_permission(
        UUID(claims["sub"]), "settings", "manage", db, tenant_id
    )
    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    method = WithdrawalMethod(
        tenant_id=tenant_id,
        name=payload.name,
        provider=payload.provider,
        method_type=payload.method_type,
        min_amount=payload.min_amount,
        max_amount=payload.max_amount,
        processing_fee_percent=payload.processing_fee_percent,
        processing_time_hours=payload.processing_time_hours,
    )

    db.add(method)
    await db.commit()
    await db.refresh(method)

    return method


@router.get("/methods", response_model=List[WithdrawalMethodResponse])
async def list_withdrawal_methods(
    claims: dict = Depends(current_claims),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Get all withdrawal methods for tenant"""

    tenant_id = UUID(claims["tenant_id"])

    result = await db.execute(
        select(WithdrawalMethod).where(WithdrawalMethod.tenant_id == tenant_id)
    )
    return result.scalars().all()


# ========== Withdrawal Transactions ==========


@router.post(
    "/", response_model=WithdrawalResponse, status_code=status.HTTP_201_CREATED
)
async def create_withdrawal(
    payload: WithdrawalCreate,
    claims: dict = Depends(current_claims),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Create new withdrawal. Requires: withdrawals.create"""

    tenant_id = UUID(claims["tenant_id"])
    user_id = UUID(claims["sub"])

    # Check permission
    has_permission = await check_permission(
        user_id, "withdrawals", "create", db, tenant_id
    )
    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    # Verify client exists
    result = await db.execute(
        select(Client).where(
            (Client.id == payload.client_id) & (Client.tenant_id == tenant_id)
        )
    )
    client = result.scalar()
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Client not found"
        )

    # Verify withdrawal method exists
    result = await db.execute(
        select(WithdrawalMethod).where(
            (WithdrawalMethod.id == payload.method_id)
            & (WithdrawalMethod.tenant_id == tenant_id)
        )
    )
    method = result.scalar()
    if not method:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Withdrawal method not found"
        )

    # Validate amount limits
    if method.min_amount and payload.amount < method.min_amount:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Amount below minimum: {method.min_amount}",
        )
    if method.max_amount and payload.amount > method.max_amount:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Amount exceeds maximum: {method.max_amount}",
        )

    # Validate sufficient balance
    if _available_client_balance(client) < payload.amount:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Insufficient balance for withdrawal",
        )

    # Calculate fees
    processing_fee = payload.amount * (method.processing_fee_percent / Decimal("100"))
    net_amount = payload.amount - processing_fee

    withdrawal = Withdrawal(
        tenant_id=tenant_id,
        client_id=payload.client_id,
        amount=payload.amount,
        currency=payload.currency,
        method_id=payload.method_id,
        method_name=method.name,
        payment_reference=payload.payment_reference,
        processing_fee=processing_fee,
        net_amount=net_amount,
    )

    db.add(withdrawal)
    await db.commit()
    await db.refresh(withdrawal)

    # Log activity
    activity = Activity(
        tenant_id=tenant_id,
        entity_type="WITHDRAWAL",
        entity_id=withdrawal.id,
        activity_type="CREATED",
        description=f"Withdrawal created: {payload.amount} {payload.currency}",
        user_id=user_id,
    )
    db.add(activity)
    await db.commit()

    return withdrawal


@router.get("/", response_model=WithdrawalListResponse)
async def list_withdrawals(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None),
    client_id: Optional[UUID] = Query(None),
    method_id: Optional[UUID] = Query(None),
    claims: dict = Depends(current_claims),
    db: AsyncSession = Depends(get_tenant_db),
):
    """List withdrawals. Requires: withdrawals.view"""

    tenant_id = UUID(claims["tenant_id"])

    # Check permission
    has_permission = await check_permission(
        UUID(claims["sub"]), "withdrawals", "view", db, tenant_id
    )
    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    query = select(Withdrawal).where(Withdrawal.tenant_id == tenant_id)

    if status:
        query = query.where(Withdrawal.status == status)

    if client_id:
        query = query.where(Withdrawal.client_id == client_id)

    if method_id:
        query = query.where(Withdrawal.method_id == method_id)

    # Count total
    count_result = await db.execute(query)
    total = len(count_result.scalars().all())

    # Paginate
    offset = (page - 1) * limit
    query = query.order_by(desc(Withdrawal.created_at)).offset(offset).limit(limit)

    result = await db.execute(query)
    withdrawals = result.scalars().all()

    return {
        "total": total,
        "page": page,
        "limit": limit,
        "items": withdrawals,
    }


@router.get("/{withdrawal_id}", response_model=WithdrawalDetailResponse)
async def get_withdrawal(
    withdrawal_id: UUID,
    claims: dict = Depends(current_claims),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Get withdrawal details. Requires: withdrawals.view"""

    tenant_id = UUID(claims["tenant_id"])

    # Check permission
    has_permission = await check_permission(
        UUID(claims["sub"]), "withdrawals", "view", db, tenant_id
    )
    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    result = await db.execute(
        select(Withdrawal).where(
            (Withdrawal.id == withdrawal_id) & (Withdrawal.tenant_id == tenant_id)
        )
    )
    withdrawal = result.scalar()

    if not withdrawal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    return withdrawal


@router.post("/{withdrawal_id}/approve", response_model=WithdrawalResponse)
async def approve_withdrawal(
    withdrawal_id: UUID,
    payload: WithdrawalApprove,
    claims: dict = Depends(current_claims),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Approve withdrawal. Requires: withdrawals.approve"""

    tenant_id = UUID(claims["tenant_id"])
    user_id = UUID(claims["sub"])

    # Check permission
    has_permission = await check_permission(
        user_id, "withdrawals", "approve", db, tenant_id
    )
    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    result = await db.execute(
        select(Withdrawal).where(
            (Withdrawal.id == withdrawal_id) & (Withdrawal.tenant_id == tenant_id)
        )
    )
    withdrawal = result.scalar()

    if not withdrawal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    if withdrawal.status != "PENDING":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot approve withdrawal with status: {withdrawal.status}",
        )

    withdrawal.status = "APPROVED"
    withdrawal.approved_by = user_id
    withdrawal.approved_at = payload.approved_at or datetime.utcnow()

    # Update client financials
    result = await db.execute(
        select(ClientFinancials).where(
            ClientFinancials.client_id == withdrawal.client_id
        )
    )
    financials = result.scalar()
    if financials:
        financials.total_withdrawals += withdrawal.net_amount
        financials.net_deposits -= withdrawal.net_amount

    # Update client totals
    result = await db.execute(select(Client).where(Client.id == withdrawal.client_id))
    client = result.scalar()
    if client:
        client.total_withdrawals = (
            client.total_withdrawals or Decimal("0")
        ) + withdrawal.net_amount
        client.net_deposits = (
            client.net_deposits or Decimal("0")
        ) - withdrawal.net_amount
        client.last_withdrawal_date = datetime.utcnow()

    await db.commit()
    await db.refresh(withdrawal)

    # Log activity
    activity = Activity(
        tenant_id=tenant_id,
        entity_type="WITHDRAWAL",
        entity_id=withdrawal.id,
        activity_type="APPROVED",
        description=f"Withdrawal approved: {withdrawal.net_amount} {withdrawal.currency}",
        user_id=user_id,
    )
    db.add(activity)
    await db.commit()

    return withdrawal


@router.post("/{withdrawal_id}/reject", response_model=WithdrawalResponse)
async def reject_withdrawal(
    withdrawal_id: UUID,
    payload: WithdrawalReject,
    claims: dict = Depends(current_claims),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Reject withdrawal. Requires: withdrawals.reject"""

    tenant_id = UUID(claims["tenant_id"])
    user_id = UUID(claims["sub"])

    # Check permission
    has_permission = await check_permission(
        user_id, "withdrawals", "reject", db, tenant_id
    )
    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    result = await db.execute(
        select(Withdrawal).where(
            (Withdrawal.id == withdrawal_id) & (Withdrawal.tenant_id == tenant_id)
        )
    )
    withdrawal = result.scalar()

    if not withdrawal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    if withdrawal.status != "PENDING":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot reject withdrawal with status: {withdrawal.status}",
        )

    withdrawal.status = "REJECTED"
    withdrawal.rejected_by = user_id
    withdrawal.rejection_reason = payload.rejection_reason

    await db.commit()
    await db.refresh(withdrawal)

    # Log activity
    activity = Activity(
        tenant_id=tenant_id,
        entity_type="WITHDRAWAL",
        entity_id=withdrawal.id,
        activity_type="REJECTED",
        description=f"Withdrawal rejected: {payload.rejection_reason}",
        user_id=user_id,
    )
    db.add(activity)
    await db.commit()

    return withdrawal


@router.post("/{withdrawal_id}/complete", response_model=WithdrawalResponse)
async def complete_withdrawal(
    withdrawal_id: UUID,
    claims: dict = Depends(current_claims),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Mark withdrawal as completed. Requires: withdrawals.approve"""

    tenant_id = UUID(claims["tenant_id"])
    user_id = UUID(claims["sub"])

    # Check permission
    has_permission = await check_permission(
        user_id, "withdrawals", "approve", db, tenant_id
    )
    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    result = await db.execute(
        select(Withdrawal).where(
            (Withdrawal.id == withdrawal_id) & (Withdrawal.tenant_id == tenant_id)
        )
    )
    withdrawal = result.scalar()

    if not withdrawal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    if withdrawal.status != "APPROVED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only approved withdrawals can be completed",
        )

    withdrawal.status = "COMPLETED"
    withdrawal.completed_at = datetime.utcnow()

    await db.commit()
    await db.refresh(withdrawal)

    # Log activity
    activity = Activity(
        tenant_id=tenant_id,
        entity_type="WITHDRAWAL",
        entity_id=withdrawal.id,
        activity_type="COMPLETED",
        description=f"Withdrawal completed: {withdrawal.net_amount} {withdrawal.currency}",
        user_id=user_id,
    )
    db.add(activity)
    await db.commit()

    return withdrawal
