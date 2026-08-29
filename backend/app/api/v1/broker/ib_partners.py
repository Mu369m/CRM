"""
IB Partner Management API Endpoints
Handles affiliate partner CRUD and commission tracking
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, and_

from app.db import get_db
from app.models.master import IBPartner
from app.middleware.rbac_enforcer import require_permission
from app.middleware.audit_logger import AuditLogger
from app.security import get_current_user
from app.schemas import IBPartnerCreate, IBPartnerUpdate, IBPartnerResponse, PaginatedResponse

router = APIRouter(prefix="/api/v1/broker/ib-partners", tags=["IB Partners"])


@router.get("", response_model=PaginatedResponse[IBPartnerResponse])
async def list_ib_partners(
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    search: str = Query("", min_length=0),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
    _=Depends(require_permission("ib.view")),
):
    """List IB partners with search and pagination"""
    query = select(IBPartner).where(IBPartner.broker_id == current_user.broker_id)

    if search:
        search_term = f"%{search}%"
        query = query.where(
            or_(
                IBPartner.first_name.ilike(search_term),
                IBPartner.last_name.ilike(search_term),
                IBPartner.email.ilike(search_term),
                IBPartner.company_name.ilike(search_term),
            )
        )

    # Get total
    count_query = select(func.count()).select_from(IBPartner).where(query.whereclause)
    result = await db.execute(count_query)
    total = result.scalar()

    # Get paginated results
    query = query.order_by(desc(IBPartner.created_at)).offset(offset).limit(limit)
    result = await db.execute(query)
    partners = result.scalars().all()

    return {
        "items": [IBPartnerResponse.from_orm(p) for p in partners],
        "total": total,
    }


@router.post("", response_model=IBPartnerResponse)
async def create_ib_partner(
    data: IBPartnerCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
    _=Depends(require_permission("ib.create")),
):
    """Create new IB partner"""
    partner = IBPartner(
        broker_id=current_user.broker_id,
        first_name=data.first_name,
        last_name=data.last_name,
        email=data.email,
        company_name=data.company_name,
        ib_level=data.ib_level,
    )

    db.add(partner)
    await db.flush()

    await AuditLogger.log_create(
        db, "IBPartner", partner.id, {"email": data.email, "level": data.ib_level}
    )

    await db.commit()
    return IBPartnerResponse.from_orm(partner)


@router.get("/{partner_id}", response_model=IBPartnerResponse)
async def get_ib_partner(
    partner_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
    _=Depends(require_permission("ib.view")),
):
    """Get single IB partner"""
    result = await db.execute(
        select(IBPartner).where(
            and_(IBPartner.id == partner_id, IBPartner.broker_id == current_user.broker_id)
        )
    )
    partner = result.scalar_one_or_none()

    if not partner:
        raise HTTPException(status_code=404, detail="Partner not found")

    return IBPartnerResponse.from_orm(partner)


@router.put("/{partner_id}", response_model=IBPartnerResponse)
async def update_ib_partner(
    partner_id: str,
    data: IBPartnerUpdate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
    _=Depends(require_permission("ib.edit")),
):
    """Update IB partner"""
    result = await db.execute(
        select(IBPartner).where(
            and_(IBPartner.id == partner_id, IBPartner.broker_id == current_user.broker_id)
        )
    )
    partner = result.scalar_one_or_none()

    if not partner:
        raise HTTPException(status_code=404, detail="Partner not found")

    changes = {}
    if data.first_name is not None:
        changes["first_name"] = data.first_name
        partner.first_name = data.first_name
    if data.last_name is not None:
        changes["last_name"] = data.last_name
        partner.last_name = data.last_name
    if data.email is not None:
        changes["email"] = data.email
        partner.email = data.email
    if data.company_name is not None:
        changes["company_name"] = data.company_name
        partner.company_name = data.company_name
    if data.ib_level is not None:
        changes["ib_level"] = data.ib_level
        partner.ib_level = data.ib_level

    await AuditLogger.log_update(db, "IBPartner", partner_id, changes)
    await db.commit()

    return IBPartnerResponse.from_orm(partner)


@router.delete("/{partner_id}")
async def delete_ib_partner(
    partner_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
    _=Depends(require_permission("ib.delete")),
):
    """Delete IB partner"""
    result = await db.execute(
        select(IBPartner).where(
            and_(IBPartner.id == partner_id, IBPartner.broker_id == current_user.broker_id)
        )
    )
    partner = result.scalar_one_or_none()

    if not partner:
        raise HTTPException(status_code=404, detail="Partner not found")

    await db.delete(partner)
    await AuditLogger.log_delete(db, "IBPartner", partner_id)
    await db.commit()

    return {"message": "Partner deleted"}
