"""
Client / Trader management API endpoints.

Allows brokers to manage trading clients and their accounts.
"""

from uuid import UUID
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, desc, and_
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field, EmailStr

from app.core.db_router import get_tenant_db
from app.security import current_claims
from app.models import (
    Campaign,
    Client,
    ClientAccount,
    ClientFinancials,
    IbPartner,
    Task,
    Note,
    Activity,
    User,
)
from app.middleware.permission_check import check_permission

router = APIRouter(prefix="/api/v1/broker/clients", tags=["Clients"])


# ========== Schemas ==========


class ClientCreate(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    phone: Optional[str] = None
    country: Optional[str] = None
    assigned_user_id: Optional[UUID] = None
    trading_platform: Optional[str] = None
    account_type: Optional[str] = None
    source: Optional[str] = None
    campaign_id: Optional[UUID] = None
    ib_partner_id: Optional[UUID] = None

    class Config:
        json_schema_extra = {
            "example": {
                "first_name": "John",
                "last_name": "Doe",
                "email": "john@example.com",
                "phone": "+1234567890",
                "country": "US",
                "trading_platform": "MT5",
                "account_type": "Standard",
            }
        }


class ClientUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    country: Optional[str] = None
    status: Optional[str] = None
    assigned_user_id: Optional[UUID] = None
    trading_platform: Optional[str] = None
    account_type: Optional[str] = None


class AddAccount(BaseModel):
    account_number: str = Field(..., min_length=1)
    platform: str = Field(..., description="MT5, MT4, etc.")
    server: Optional[str] = None
    leverage: Optional[int] = None

    class Config:
        json_schema_extra = {
            "example": {
                "account_number": "12345678",
                "platform": "MT5",
                "server": "DemoServer",
                "leverage": 1,
            }
        }


class UpdateAccount(BaseModel):
    trading_status: Optional[str] = None
    leverage: Optional[int] = None
    server: Optional[str] = None


class ClientAccountResponse(BaseModel):
    id: UUID
    client_id: UUID
    account_number: str
    platform: str
    server: Optional[str]
    trading_status: Optional[str]
    account_balance: Optional[float]
    equity: Optional[float]
    leverage: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True


class ClientFinancialsResponse(BaseModel):
    total_deposits: float
    total_withdrawals: float
    net_deposits: float
    total_trading_volume: float
    total_commissions_paid: float
    total_profit_loss: float
    last_updated: datetime

    class Config:
        from_attributes = True


class ClientResponse(BaseModel):
    id: UUID
    first_name: str
    last_name: str
    email: str
    phone: Optional[str]
    country: Optional[str]
    status: str
    source: Optional[str]
    assigned_user_id: Optional[UUID]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ClientDetailResponse(ClientResponse):
    accounts: List[ClientAccountResponse]
    financials: Optional[ClientFinancialsResponse]
    trading_platform: Optional[str]
    account_type: Optional[str]


class ClientListResponse(BaseModel):
    total: int
    page: int
    limit: int
    items: List[ClientResponse]


# ========== Endpoints ==========


@router.post("/", response_model=ClientResponse, status_code=status.HTTP_201_CREATED)
async def create_client(
    payload: ClientCreate,
    claims: dict = Depends(current_claims),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Create new client. Requires: clients.create"""

    tenant_id = UUID(claims["tenant_id"])
    user_id = UUID(claims["sub"])

    # Check permission
    has_permission = await check_permission(user_id, "clients", "create", db, tenant_id)
    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    if payload.assigned_user_id and not await db.scalar(
        select(User).where(
            User.id == payload.assigned_user_id, User.tenant_id == tenant_id
        )
    ):
        raise HTTPException(
            status_code=400, detail="Assigned user is invalid for this tenant"
        )
    if payload.campaign_id and not await db.scalar(
        select(Campaign).where(
            Campaign.id == payload.campaign_id, Campaign.tenant_id == tenant_id
        )
    ):
        raise HTTPException(
            status_code=400, detail="Campaign is invalid for this tenant"
        )
    if payload.ib_partner_id and not await db.scalar(
        select(IbPartner).where(
            IbPartner.id == payload.ib_partner_id, IbPartner.tenant_id == tenant_id
        )
    ):
        raise HTTPException(
            status_code=400, detail="IB partner is invalid for this tenant"
        )

    # Check if email already exists
    result = await db.execute(
        select(Client).where(
            (Client.email == payload.email) & (Client.tenant_id == tenant_id)
        )
    )
    if result.scalar():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Email already exists"
        )

    client = Client(
        tenant_id=tenant_id,
        first_name=payload.first_name,
        last_name=payload.last_name,
        email=payload.email,
        phone=payload.phone,
        country=payload.country,
        assigned_user_id=payload.assigned_user_id,
        trading_platform=payload.trading_platform,
        account_type=payload.account_type,
        source=payload.source,
        campaign_id=payload.campaign_id,
        ib_partner_id=payload.ib_partner_id,
    )

    db.add(client)
    await db.commit()
    await db.refresh(client)

    # Create financials record
    financials = ClientFinancials(
        tenant_id=tenant_id,
        client_id=client.id,
    )
    db.add(financials)

    # Log activity
    activity = Activity(
        tenant_id=tenant_id,
        entity_type="CLIENT",
        entity_id=client.id,
        activity_type="CREATED",
        description=f"Client created: {payload.first_name} {payload.last_name}",
        user_id=user_id,
    )
    db.add(activity)
    await db.commit()

    return client


@router.get("/", response_model=ClientListResponse)
async def list_clients(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    country: Optional[str] = Query(None),
    assigned_to_id: Optional[UUID] = Query(None),
    is_archived: bool = Query(False),
    claims: dict = Depends(current_claims),
    db: AsyncSession = Depends(get_tenant_db),
):
    """List clients with filtering. Requires: clients.view"""

    tenant_id = UUID(claims["tenant_id"])

    # Check permission
    has_permission = await check_permission(
        UUID(claims["sub"]), "clients", "view", db, tenant_id
    )
    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    query = select(Client).where(
        (Client.tenant_id == tenant_id) & (Client.is_archived == is_archived)
    )

    if search:
        search_term = f"%{search}%"
        query = query.where(
            (Client.email.ilike(search_term))
            | (Client.first_name.ilike(search_term))
            | (Client.last_name.ilike(search_term))
            | (Client.phone.ilike(search_term))
        )

    if status:
        query = query.where(Client.status == status)

    if country:
        query = query.where(Client.country == country)

    if assigned_to_id:
        query = query.where(Client.assigned_user_id == assigned_to_id)

    # Count total
    count_query = query
    count_result = await db.execute(count_query)
    total = len(count_result.scalars().all())

    # Paginate
    offset = (page - 1) * limit
    query = query.order_by(desc(Client.created_at)).offset(offset).limit(limit)

    result = await db.execute(query)
    clients = result.scalars().all()

    return {
        "total": total,
        "page": page,
        "limit": limit,
        "items": clients,
    }


@router.get("/{client_id}", response_model=ClientDetailResponse)
async def get_client(
    client_id: UUID,
    claims: dict = Depends(current_claims),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Get client details with accounts and financials. Requires: clients.view"""

    tenant_id = UUID(claims["tenant_id"])

    # Check permission
    has_permission = await check_permission(
        UUID(claims["sub"]), "clients", "view", db, tenant_id
    )
    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    result = await db.execute(
        select(Client).where((Client.id == client_id) & (Client.tenant_id == tenant_id))
    )
    client = result.scalar()

    if not client:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    # Get accounts
    result = await db.execute(
        select(ClientAccount).where(ClientAccount.client_id == client_id)
    )
    accounts = result.scalars().all()

    # Get financials
    result = await db.execute(
        select(ClientFinancials).where(ClientFinancials.client_id == client_id)
    )
    financials = result.scalar()

    return ClientDetailResponse(
        **{**client.__dict__, "accounts": accounts, "financials": financials}
    )


@router.put("/{client_id}", response_model=ClientResponse)
async def update_client(
    client_id: UUID,
    payload: ClientUpdate,
    claims: dict = Depends(current_claims),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Update client. Requires: clients.edit"""

    tenant_id = UUID(claims["tenant_id"])
    user_id = UUID(claims["sub"])

    # Check permission
    has_permission = await check_permission(user_id, "clients", "edit", db, tenant_id)
    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    result = await db.execute(
        select(Client).where((Client.id == client_id) & (Client.tenant_id == tenant_id))
    )
    client = result.scalar()

    if not client:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    if payload.assigned_user_id and not await db.scalar(
        select(User).where(
            User.id == payload.assigned_user_id, User.tenant_id == tenant_id
        )
    ):
        raise HTTPException(
            status_code=400, detail="Assigned user is invalid for this tenant"
        )
    if payload.campaign_id and not await db.scalar(
        select(Campaign).where(
            Campaign.id == payload.campaign_id, Campaign.tenant_id == tenant_id
        )
    ):
        raise HTTPException(
            status_code=400, detail="Campaign is invalid for this tenant"
        )
    if payload.ib_partner_id and not await db.scalar(
        select(IbPartner).where(
            IbPartner.id == payload.ib_partner_id, IbPartner.tenant_id == tenant_id
        )
    ):
        raise HTTPException(
            status_code=400, detail="IB partner is invalid for this tenant"
        )

    # Track changes
    changes = []

    update_data = payload.dict(exclude_unset=True)
    for key, value in update_data.items():
        old_value = getattr(client, key)
        if old_value != value:
            changes.append(f"{key}: {old_value} -> {value}")
        setattr(client, key, value)

    client.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(client)

    # Log activity if there were changes
    if changes:
        activity = Activity(
            tenant_id=tenant_id,
            entity_type="CLIENT",
            entity_id=client.id,
            activity_type="UPDATED",
            description=f"Client updated: {', '.join(changes)}",
            user_id=user_id,
        )
        db.add(activity)
        await db.commit()

    return client


@router.delete("/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
async def archive_client(
    client_id: UUID,
    claims: dict = Depends(current_claims),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Archive client (soft delete). Requires: clients.delete"""

    tenant_id = UUID(claims["tenant_id"])
    user_id = UUID(claims["sub"])

    # Check permission
    has_permission = await check_permission(user_id, "clients", "delete", db, tenant_id)
    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    result = await db.execute(
        select(Client).where((Client.id == client_id) & (Client.tenant_id == tenant_id))
    )
    client = result.scalar()

    if not client:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    client.is_archived = True
    await db.commit()

    # Log activity
    activity = Activity(
        tenant_id=tenant_id,
        entity_type="CLIENT",
        entity_id=client.id,
        activity_type="ARCHIVED",
        description="Client archived",
        user_id=user_id,
    )
    db.add(activity)
    await db.commit()


# ========== Client Accounts ==========


@router.post(
    "/{client_id}/accounts",
    response_model=ClientAccountResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_client_account(
    client_id: UUID,
    payload: AddAccount,
    claims: dict = Depends(current_claims),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Add trading account to client"""

    tenant_id = UUID(claims["tenant_id"])

    # Verify client exists
    result = await db.execute(
        select(Client).where((Client.id == client_id) & (Client.tenant_id == tenant_id))
    )
    if not result.scalar():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Client not found"
        )

    # Check if account number already exists
    result = await db.execute(
        select(ClientAccount).where(
            (ClientAccount.account_number == payload.account_number)
            & (ClientAccount.tenant_id == tenant_id)
        )
    )
    if result.scalar():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Account number already exists"
        )

    account = ClientAccount(
        tenant_id=tenant_id,
        client_id=client_id,
        account_number=payload.account_number,
        platform=payload.platform,
        server=payload.server,
        leverage=payload.leverage,
    )

    db.add(account)
    await db.commit()
    await db.refresh(account)

    return account


@router.get("/{client_id}/accounts", response_model=List[ClientAccountResponse])
async def get_client_accounts(
    client_id: UUID,
    claims: dict = Depends(current_claims),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Get all accounts for client"""

    tenant_id = UUID(claims["tenant_id"])

    # Verify client exists
    result = await db.execute(
        select(Client).where((Client.id == client_id) & (Client.tenant_id == tenant_id))
    )
    if not result.scalar():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Client not found"
        )

    result = await db.execute(
        select(ClientAccount).where(ClientAccount.client_id == client_id)
    )
    return result.scalars().all()


@router.put("/{client_id}/accounts/{account_id}", response_model=ClientAccountResponse)
async def update_client_account(
    client_id: UUID,
    account_id: UUID,
    payload: UpdateAccount,
    claims: dict = Depends(current_claims),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Update account details"""

    tenant_id = UUID(claims["tenant_id"])

    result = await db.execute(
        select(ClientAccount).where(
            (ClientAccount.id == account_id)
            & (ClientAccount.client_id == client_id)
            & (ClientAccount.tenant_id == tenant_id)
        )
    )
    account = result.scalar()

    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    update_data = payload.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(account, key, value)

    account.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(account)

    return account


@router.delete(
    "/{client_id}/accounts/{account_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_client_account(
    client_id: UUID,
    account_id: UUID,
    claims: dict = Depends(current_claims),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Delete client account"""

    tenant_id = UUID(claims["tenant_id"])

    result = await db.execute(
        select(ClientAccount).where(
            (ClientAccount.id == account_id)
            & (ClientAccount.client_id == client_id)
            & (ClientAccount.tenant_id == tenant_id)
        )
    )
    account = result.scalar()

    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    await db.delete(account)
    await db.commit()
