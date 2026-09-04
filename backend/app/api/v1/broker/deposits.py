"""
Deposit management API endpoints.

Handles client deposit processing, approval workflows, and financial tracking.
"""

from uuid import UUID
from datetime import datetime
from typing import Optional, List
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, desc, and_
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from app.core.db_router import get_tenant_db
from app.security import current_claims
from app.models import (
    Deposit,
    DepositMethod,
    Client,
    Activity,
    ClientFinancials,
)
from app.middleware.permission_check import check_permission

router = APIRouter(prefix="/api/v1/broker/deposits", tags=["Deposits"])


# ========== Schemas ==========


class DepositMethodCreate(BaseModel):
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
                "name": "Visa/Mastercard",
                "provider": "Stripe",
                "method_type": "CARD",
                "processing_fee_percent": Decimal("2.5"),
                "processing_time_hours": 1,
            }
        }


class DepositCreate(BaseModel):
    client_id: UUID
    amount: Decimal = Field(..., gt=0)
    currency: str = Field(..., min_length=3, max_length=3)
    method_id: UUID
    payment_reference: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "client_id": "550e8400-e29b-41d4-a716-446655440000",
                "amount": Decimal("1000.00"),
                "currency": "USD",
                "method_id": "550e8400-e29b-41d4-a716-446655440001",
            }
        }


class DepositApprove(BaseModel):
    approved_at: Optional[datetime] = None


class DepositReject(BaseModel):
    rejection_reason: str = Field(..., max_length=500)


class DepositMethodResponse(BaseModel):
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


class DepositResponse(BaseModel):
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


class DepositDetailResponse(DepositResponse):
    payment_reference: Optional[str]
    rejection_reason: Optional[str]
    approved_by: Optional[UUID]
    rejected_by: Optional[UUID]


class DepositListResponse(BaseModel):
    total: int
    page: int
    limit: int
    items: List[DepositResponse]


# ========== Deposit Method Management ==========


@router.post(
    "/methods",
    response_model=DepositMethodResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_deposit_method(
    payload: DepositMethodCreate,
    claims: dict = Depends(current_claims),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Create deposit payment method. Requires: settings.manage"""

    tenant_id = UUID(claims["tenant_id"])

    # Check permission
    has_permission = await check_permission(
        UUID(claims["sub"]), "settings", "manage", db, tenant_id
    )
    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    method = DepositMethod(
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


@router.get("/methods", response_model=List[DepositMethodResponse])
async def list_deposit_methods(
    claims: dict = Depends(current_claims),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Get all deposit methods for tenant"""

    tenant_id = UUID(claims["tenant_id"])

    result = await db.execute(
        select(DepositMethod).where(DepositMethod.tenant_id == tenant_id)
    )
    return result.scalars().all()


# ========== Deposit Transactions ==========


@router.post("/", response_model=DepositResponse, status_code=status.HTTP_201_CREATED)
async def create_deposit(
    payload: DepositCreate,
    claims: dict = Depends(current_claims),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Create new deposit. Requires: deposits.create"""

    tenant_id = UUID(claims["tenant_id"])
    user_id = UUID(claims["sub"])

    # Check permission
    has_permission = await check_permission(
        user_id, "deposits", "create", db, tenant_id
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

    # Verify deposit method exists
    result = await db.execute(
        select(DepositMethod).where(
            (DepositMethod.id == payload.method_id)
            & (DepositMethod.tenant_id == tenant_id)
        )
    )
    method = result.scalar()
    if not method:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Deposit method not found"
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

    # Calculate fees
    processing_fee = payload.amount * (method.processing_fee_percent / Decimal("100"))
    net_amount = payload.amount - processing_fee

    deposit = Deposit(
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

    db.add(deposit)
    await db.commit()
    await db.refresh(deposit)

    # Log activity
    activity = Activity(
        tenant_id=tenant_id,
        entity_type="DEPOSIT",
        entity_id=deposit.id,
        activity_type="CREATED",
        description=f"Deposit created: {payload.amount} {payload.currency}",
        user_id=user_id,
    )
    db.add(activity)
    await db.commit()

    return deposit


@router.get("/", response_model=DepositListResponse)
async def list_deposits(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None),
    client_id: Optional[UUID] = Query(None),
    method_id: Optional[UUID] = Query(None),
    claims: dict = Depends(current_claims),
    db: AsyncSession = Depends(get_tenant_db),
):
    """List deposits. Requires: deposits.view"""

    tenant_id = UUID(claims["tenant_id"])

    # Check permission
    has_permission = await check_permission(
        UUID(claims["sub"]), "deposits", "view", db, tenant_id
    )
    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    query = select(Deposit).where(Deposit.tenant_id == tenant_id)

    if status:
        query = query.where(Deposit.status == status)

    if client_id:
        query = query.where(Deposit.client_id == client_id)

    if method_id:
        query = query.where(Deposit.method_id == method_id)

    # Count total
    count_result = await db.execute(query)
    total = len(count_result.scalars().all())

    # Paginate
    offset = (page - 1) * limit
    query = query.order_by(desc(Deposit.created_at)).offset(offset).limit(limit)

    result = await db.execute(query)
    deposits = result.scalars().all()

    return {
        "total": total,
        "page": page,
        "limit": limit,
        "items": deposits,
    }


@router.get("/{deposit_id}", response_model=DepositDetailResponse)
async def get_deposit(
    deposit_id: UUID,
    claims: dict = Depends(current_claims),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Get deposit details. Requires: deposits.view"""

    tenant_id = UUID(claims["tenant_id"])

    # Check permission
    has_permission = await check_permission(
        UUID(claims["sub"]), "deposits", "view", db, tenant_id
    )
    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    result = await db.execute(
        select(Deposit).where(
            (Deposit.id == deposit_id) & (Deposit.tenant_id == tenant_id)
        )
    )
    deposit = result.scalar()

    if not deposit:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    return deposit


@router.post("/{deposit_id}/approve", response_model=DepositResponse)
async def approve_deposit(
    deposit_id: UUID,
    payload: DepositApprove,
    claims: dict = Depends(current_claims),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Approve deposit. Requires: deposits.approve"""

    tenant_id = UUID(claims["tenant_id"])
    user_id = UUID(claims["sub"])

    # Check permission
    has_permission = await check_permission(
        user_id, "deposits", "approve", db, tenant_id
    )
    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    result = await db.execute(
        select(Deposit).where(
            (Deposit.id == deposit_id) & (Deposit.tenant_id == tenant_id)
        )
    )
    deposit = result.scalar()

    if not deposit:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    if deposit.status != "PENDING":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot approve deposit with status: {deposit.status}",
        )

    deposit.status = "APPROVED"
    deposit.approved_by = user_id
    deposit.approved_at = payload.approved_at or datetime.utcnow()

    # Update client financials
    result = await db.execute(
        select(ClientFinancials).where(ClientFinancials.client_id == deposit.client_id)
    )
    financials = result.scalar()
    if financials:
        financials.total_deposits += deposit.net_amount
        financials.net_deposits += deposit.net_amount

    # Update client totals
    result = await db.execute(select(Client).where(Client.id == deposit.client_id))
    client = result.scalar()
    if client:
        client.total_deposits = (
            client.total_deposits or Decimal("0")
        ) + deposit.net_amount
        client.net_deposits = (client.net_deposits or Decimal("0")) + deposit.net_amount
        client.last_deposit_date = datetime.utcnow()

    await db.commit()
    await db.refresh(deposit)

    # Log activity
    activity = Activity(
        tenant_id=tenant_id,
        entity_type="DEPOSIT",
        entity_id=deposit.id,
        activity_type="APPROVED",
        description=f"Deposit approved: {deposit.net_amount} {deposit.currency}",
        user_id=user_id,
    )
    db.add(activity)
    await db.commit()

    return deposit


@router.post("/{deposit_id}/reject", response_model=DepositResponse)
async def reject_deposit(
    deposit_id: UUID,
    payload: DepositReject,
    claims: dict = Depends(current_claims),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Reject deposit. Requires: deposits.reject"""

    tenant_id = UUID(claims["tenant_id"])
    user_id = UUID(claims["sub"])

    # Check permission
    has_permission = await check_permission(
        user_id, "deposits", "reject", db, tenant_id
    )
    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    result = await db.execute(
        select(Deposit).where(
            (Deposit.id == deposit_id) & (Deposit.tenant_id == tenant_id)
        )
    )
    deposit = result.scalar()

    if not deposit:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    if deposit.status != "PENDING":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot reject deposit with status: {deposit.status}",
        )

    deposit.status = "REJECTED"
    deposit.rejected_by = user_id
    deposit.rejection_reason = payload.rejection_reason

    await db.commit()
    await db.refresh(deposit)

    # Log activity
    activity = Activity(
        tenant_id=tenant_id,
        entity_type="DEPOSIT",
        entity_id=deposit.id,
        activity_type="REJECTED",
        description=f"Deposit rejected: {payload.rejection_reason}",
        user_id=user_id,
    )
    db.add(activity)
    await db.commit()

    return deposit


@router.post("/{deposit_id}/complete", response_model=DepositResponse)
async def complete_deposit(
    deposit_id: UUID,
    claims: dict = Depends(current_claims),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Mark deposit as completed. Requires: deposits.approve"""

    tenant_id = UUID(claims["tenant_id"])
    user_id = UUID(claims["sub"])

    # Check permission
    has_permission = await check_permission(
        user_id, "deposits", "approve", db, tenant_id
    )
    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    result = await db.execute(
        select(Deposit).where(
            (Deposit.id == deposit_id) & (Deposit.tenant_id == tenant_id)
        )
    )
    deposit = result.scalar()

    if not deposit:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    if deposit.status != "APPROVED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only approved deposits can be completed",
        )

    deposit.status = "COMPLETED"
    deposit.completed_at = datetime.utcnow()

    await db.commit()
    await db.refresh(deposit)

    # Log activity
    activity = Activity(
        tenant_id=tenant_id,
        entity_type="DEPOSIT",
        entity_id=deposit.id,
        activity_type="COMPLETED",
        description=f"Deposit completed: {deposit.net_amount} {deposit.currency}",
        user_id=user_id,
    )
    db.add(activity)
    await db.commit()

    return deposit
