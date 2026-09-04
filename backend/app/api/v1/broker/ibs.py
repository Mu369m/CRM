"""
IB / Affiliate Partner management API endpoints.

Allows brokers to manage IB/affiliate partners and track referral commissions.
"""

from uuid import UUID
from datetime import datetime
from typing import Optional, List
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, desc, and_, func
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field, EmailStr

from app.core.db_router import get_tenant_db
from app.security import current_claims
from app.models import (
    IBPartner,
    IBRelationship,
    IBCommission,
    IBPayout,
    Client,
    Activity,
)
from app.middleware.permission_check import check_permission

router = APIRouter(prefix="/api/v1/broker/ibs", tags=["IB Partners"])


# ========== Schemas ==========


class IBPartnerCreate(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    phone: Optional[str] = None
    company_name: Optional[str] = None
    country: Optional[str] = None
    parent_ib_id: Optional[UUID] = None

    class Config:
        json_schema_extra = {
            "example": {
                "first_name": "Jane",
                "last_name": "Smith",
                "email": "jane@ib.com",
                "company_name": "JSM Trading",
                "country": "UK",
            }
        }


class IBPartnerUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    company_name: Optional[str] = None
    status: Optional[str] = None
    commission_tier: Optional[str] = None
    bank_account: Optional[str] = None
    payment_method: Optional[str] = None


class IBCommissionCreate(BaseModel):
    commission_type: str = Field(..., description="DEPOSIT, SPREAD, VOLUME, etc.")
    base_rate: Decimal = Field(..., decimal_places=4)
    tier_level: Optional[int] = None
    min_turnover: Optional[Decimal] = None
    max_turnover: Optional[Decimal] = None
    effective_from: datetime = Field(...)

    class Config:
        json_schema_extra = {
            "example": {
                "commission_type": "DEPOSIT",
                "base_rate": Decimal("0.01"),
                "effective_from": "2026-01-01T00:00:00Z",
            }
        }


class AssignClientCreate(BaseModel):
    client_id: UUID


class IBPartnerResponse(BaseModel):
    id: UUID
    first_name: str
    last_name: str
    email: str
    phone: Optional[str]
    company_name: Optional[str]
    country: Optional[str]
    status: str
    commission_tier: Optional[str]
    total_clients: int
    total_commissions: float
    total_deposits_referred: float
    created_at: datetime

    class Config:
        from_attributes = True


class IBCommissionResponse(BaseModel):
    id: UUID
    ib_partner_id: UUID
    commission_type: str
    base_rate: float
    tier_level: Optional[int]
    min_turnover: Optional[float]
    max_turnover: Optional[float]
    is_active: bool
    effective_from: datetime
    effective_to: Optional[datetime]

    class Config:
        from_attributes = True


class IBPayoutResponse(BaseModel):
    id: UUID
    ib_partner_id: UUID
    payout_period: str
    total_commissions: float
    total_clients_referred: int
    status: str
    payment_status: str
    payment_date: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class IBPartnerDetailResponse(IBPartnerResponse):
    commissions: List[IBCommissionResponse]
    payouts: List[IBPayoutResponse]
    assigned_clients: int


class IBListResponse(BaseModel):
    total: int
    page: int
    limit: int
    items: List[IBPartnerResponse]


# ========== Endpoints ==========


@router.post("/", response_model=IBPartnerResponse, status_code=status.HTTP_201_CREATED)
async def create_ib_partner(
    payload: IBPartnerCreate,
    claims: dict = Depends(current_claims),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Create new IB partner. Requires: ib.create"""

    tenant_id = UUID(claims["tenant_id"])
    user_id = UUID(claims["sub"])

    # Check permission
    has_permission = await check_permission(user_id, "ib", "create", db, tenant_id)
    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    # Check if email already exists
    result = await db.execute(
        select(IBPartner).where(
            (IBPartner.email == payload.email) & (IBPartner.tenant_id == tenant_id)
        )
    )
    if result.scalar():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Email already exists"
        )

    # Validate parent IB if provided
    if payload.parent_ib_id:
        result = await db.execute(
            select(IBPartner).where(
                (IBPartner.id == payload.parent_ib_id)
                & (IBPartner.tenant_id == tenant_id)
            )
        )
        if not result.scalar():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Parent IB not found"
            )

    ib = IBPartner(
        tenant_id=tenant_id,
        first_name=payload.first_name,
        last_name=payload.last_name,
        email=payload.email,
        phone=payload.phone,
        company_name=payload.company_name,
        country=payload.country,
        parent_ib_id=payload.parent_ib_id,
    )

    db.add(ib)
    await db.commit()
    await db.refresh(ib)

    # Log activity
    activity = Activity(
        tenant_id=tenant_id,
        entity_type="IB_PARTNER",
        entity_id=ib.id,
        activity_type="CREATED",
        description=f"IB Partner created: {payload.first_name} {payload.last_name}",
        user_id=user_id,
    )
    db.add(activity)
    await db.commit()

    return ib


@router.get("/", response_model=IBListResponse)
async def list_ib_partners(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    is_archived: bool = Query(False),
    claims: dict = Depends(current_claims),
    db: AsyncSession = Depends(get_tenant_db),
):
    """List IB partners. Requires: ib.view"""

    tenant_id = UUID(claims["tenant_id"])

    # Check permission
    has_permission = await check_permission(
        UUID(claims["sub"]), "ib", "view", db, tenant_id
    )
    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    query = select(IBPartner).where(
        (IBPartner.tenant_id == tenant_id) & (IBPartner.is_archived == is_archived)
    )

    if search:
        search_term = f"%{search}%"
        query = query.where(
            (IBPartner.email.ilike(search_term))
            | (IBPartner.first_name.ilike(search_term))
            | (IBPartner.last_name.ilike(search_term))
            | (IBPartner.company_name.ilike(search_term))
        )

    if status:
        query = query.where(IBPartner.status == status)

    # Count total
    count_query = query
    count_result = await db.execute(count_query)
    total = len(count_result.scalars().all())

    # Paginate
    offset = (page - 1) * limit
    query = query.order_by(desc(IBPartner.created_at)).offset(offset).limit(limit)

    result = await db.execute(query)
    ibs = result.scalars().all()

    return {
        "total": total,
        "page": page,
        "limit": limit,
        "items": ibs,
    }


@router.get("/{ib_id}", response_model=IBPartnerDetailResponse)
async def get_ib_partner(
    ib_id: UUID,
    claims: dict = Depends(current_claims),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Get IB partner details. Requires: ib.view"""

    tenant_id = UUID(claims["tenant_id"])

    # Check permission
    has_permission = await check_permission(
        UUID(claims["sub"]), "ib", "view", db, tenant_id
    )
    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    result = await db.execute(
        select(IBPartner).where(
            (IBPartner.id == ib_id) & (IBPartner.tenant_id == tenant_id)
        )
    )
    ib = result.scalar()

    if not ib:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    # Get commissions
    result = await db.execute(
        select(IBCommission).where(IBCommission.ib_partner_id == ib_id)
    )
    commissions = result.scalars().all()

    # Get payouts
    result = await db.execute(select(IBPayout).where(IBPayout.ib_partner_id == ib_id))
    payouts = result.scalars().all()

    # Count assigned clients
    result = await db.execute(
        select(func.count(IBRelationship.id)).where(
            IBRelationship.ib_partner_id == ib_id
        )
    )
    assigned_clients = result.scalar() or 0

    return IBPartnerDetailResponse(
        **{
            **ib.__dict__,
            "commissions": commissions,
            "payouts": payouts,
            "assigned_clients": assigned_clients,
        }
    )


@router.put("/{ib_id}", response_model=IBPartnerResponse)
async def update_ib_partner(
    ib_id: UUID,
    payload: IBPartnerUpdate,
    claims: dict = Depends(current_claims),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Update IB partner. Requires: ib.edit"""

    tenant_id = UUID(claims["tenant_id"])
    user_id = UUID(claims["sub"])

    # Check permission
    has_permission = await check_permission(user_id, "ib", "edit", db, tenant_id)
    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    result = await db.execute(
        select(IBPartner).where(
            (IBPartner.id == ib_id) & (IBPartner.tenant_id == tenant_id)
        )
    )
    ib = result.scalar()

    if not ib:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    # Track changes
    changes = []

    update_data = payload.dict(exclude_unset=True)
    for key, value in update_data.items():
        old_value = getattr(ib, key)
        if old_value != value:
            changes.append(f"{key}: {old_value} -> {value}")
        setattr(ib, key, value)

    ib.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(ib)

    # Log activity
    if changes:
        activity = Activity(
            tenant_id=tenant_id,
            entity_type="IB_PARTNER",
            entity_id=ib.id,
            activity_type="UPDATED",
            description=f"IB Partner updated: {', '.join(changes)}",
            user_id=user_id,
        )
        db.add(activity)
        await db.commit()

    return ib


@router.delete("/{ib_id}", status_code=status.HTTP_204_NO_CONTENT)
async def archive_ib_partner(
    ib_id: UUID,
    claims: dict = Depends(current_claims),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Archive IB partner. Requires: ib.delete"""

    tenant_id = UUID(claims["tenant_id"])
    user_id = UUID(claims["sub"])

    # Check permission
    has_permission = await check_permission(user_id, "ib", "delete", db, tenant_id)
    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    result = await db.execute(
        select(IBPartner).where(
            (IBPartner.id == ib_id) & (IBPartner.tenant_id == tenant_id)
        )
    )
    ib = result.scalar()

    if not ib:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    ib.is_archived = True
    await db.commit()

    # Log activity
    activity = Activity(
        tenant_id=tenant_id,
        entity_type="IB_PARTNER",
        entity_id=ib.id,
        activity_type="ARCHIVED",
        description="IB Partner archived",
        user_id=user_id,
    )
    db.add(activity)
    await db.commit()


# ========== Commission Management ==========


@router.post(
    "/{ib_id}/commissions",
    response_model=IBCommissionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_commission_rule(
    ib_id: UUID,
    payload: IBCommissionCreate,
    claims: dict = Depends(current_claims),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Create commission rule for IB. Requires: ib.edit"""

    tenant_id = UUID(claims["tenant_id"])

    # Verify IB exists
    result = await db.execute(
        select(IBPartner).where(
            (IBPartner.id == ib_id) & (IBPartner.tenant_id == tenant_id)
        )
    )
    if not result.scalar():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="IB Partner not found"
        )

    commission = IBCommission(
        tenant_id=tenant_id,
        ib_partner_id=ib_id,
        commission_type=payload.commission_type,
        base_rate=payload.base_rate,
        tier_level=payload.tier_level,
        min_turnover=payload.min_turnover,
        max_turnover=payload.max_turnover,
        effective_from=payload.effective_from,
    )

    db.add(commission)
    await db.commit()
    await db.refresh(commission)

    return commission


@router.get("/{ib_id}/commissions", response_model=List[IBCommissionResponse])
async def get_commission_rules(
    ib_id: UUID,
    claims: dict = Depends(current_claims),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Get commission rules for IB"""

    tenant_id = UUID(claims["tenant_id"])

    # Verify IB exists
    result = await db.execute(
        select(IBPartner).where(
            (IBPartner.id == ib_id) & (IBPartner.tenant_id == tenant_id)
        )
    )
    if not result.scalar():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="IB Partner not found"
        )

    result = await db.execute(
        select(IBCommission).where(IBCommission.ib_partner_id == ib_id)
    )
    return result.scalars().all()


# ========== Client Assignment ==========


@router.post("/{ib_id}/clients", status_code=status.HTTP_201_CREATED)
async def assign_client_to_ib(
    ib_id: UUID,
    payload: AssignClientCreate,
    claims: dict = Depends(current_claims),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Assign client to IB. Requires: ib.edit"""

    tenant_id = UUID(claims["tenant_id"])

    # Verify IB exists
    result = await db.execute(
        select(IBPartner).where(
            (IBPartner.id == ib_id) & (IBPartner.tenant_id == tenant_id)
        )
    )
    ib = result.scalar()
    if not ib:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="IB Partner not found"
        )

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

    # Check if relationship already exists
    result = await db.execute(
        select(IBRelationship).where(
            (IBRelationship.ib_partner_id == ib_id)
            & (IBRelationship.client_id == payload.client_id)
        )
    )
    if result.scalar():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Client already assigned to this IB",
        )

    relationship = IBRelationship(
        tenant_id=tenant_id,
        ib_partner_id=ib_id,
        client_id=payload.client_id,
    )

    # Update client's ib_partner_id
    client.ib_partner_id = ib_id

    # Update IB's total clients
    ib.total_clients += 1

    db.add(relationship)
    await db.commit()

    return {"message": "Client assigned to IB"}


@router.get("/{ib_id}/clients")
async def get_ib_clients(
    ib_id: UUID,
    claims: dict = Depends(current_claims),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Get all clients assigned to IB"""

    tenant_id = UUID(claims["tenant_id"])

    # Verify IB exists
    result = await db.execute(
        select(IBPartner).where(
            (IBPartner.id == ib_id) & (IBPartner.tenant_id == tenant_id)
        )
    )
    if not result.scalar():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="IB Partner not found"
        )

    result = await db.execute(
        select(Client).where(
            (Client.ib_partner_id == ib_id) & (Client.tenant_id == tenant_id)
        )
    )
    return result.scalars().all()


# ========== Payout Management ==========


@router.get("/{ib_id}/payouts", response_model=List[IBPayoutResponse])
async def get_ib_payouts(
    ib_id: UUID,
    claims: dict = Depends(current_claims),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Get payouts for IB"""

    tenant_id = UUID(claims["tenant_id"])

    # Verify IB exists
    result = await db.execute(
        select(IBPartner).where(
            (IBPartner.id == ib_id) & (IBPartner.tenant_id == tenant_id)
        )
    )
    if not result.scalar():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="IB Partner not found"
        )

    result = await db.execute(select(IBPayout).where(IBPayout.ib_partner_id == ib_id))
    return result.scalars().all()
