"""Audit logging API endpoints."""

from datetime import datetime
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.core.db_router import get_tenant_db
from app.models import AuditLog
from app.security import current_claims
from app.middleware.permission_check import check_permission

router = APIRouter(prefix="/api/v1/broker/audit", tags=["Audit"])


class AuditLogResponse(BaseModel):
    id: UUID
    actor_id: UUID
    action: str
    metadata_json: str
    created_at: datetime

    class Config:
        from_attributes = True


class AuditLogPage(BaseModel):
    total: int
    offset: int
    limit: int
    items: List[AuditLogResponse]


@router.get("/logs", response_model=AuditLogPage)
async def list_audit_logs(
    claims: dict = Depends(current_claims),
    db: AsyncSession = Depends(get_tenant_db),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=500),
    action: str | None = Query(default=None),
):
    """
    List audit logs for the tenant.
    Requires: settings.manage
    """
    tenant_id = UUID(claims["tenant_id"])
    user_id = UUID(claims["sub"])
    
    # Check permission
    has_permission = await check_permission(
        user_id, "settings", "manage", db, tenant_id
    )
    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    
    # Build query
    query = select(AuditLog).where(AuditLog.tenant_id == tenant_id)
    
    if action:
        query = query.where(AuditLog.action.ilike(f"%{action}%"))
    
    # Get total count
    total = await db.scalar(
        select(func.count(AuditLog.id)).where(AuditLog.tenant_id == tenant_id)
    )
    
    # Get paginated results (newest first)
    logs = await db.scalars(
        query.order_by(AuditLog.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    
    return AuditLogPage(
        total=total or 0,
        offset=offset,
        limit=limit,
        items=list(logs)
    )


@router.get("/logs/summary")
async def audit_summary(
    claims: dict = Depends(current_claims),
    db: AsyncSession = Depends(get_tenant_db),
):
    """
    Get summary statistics of recent audit activity.
    """
    tenant_id = UUID(claims["tenant_id"])
    user_id = UUID(claims["sub"])
    
    # Check permission
    has_permission = await check_permission(
        user_id, "settings", "manage", db, tenant_id
    )
    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    
    # Count by action type
    query = select(
        AuditLog.action,
        func.count(AuditLog.id).label("count")
    ).where(
        AuditLog.tenant_id == tenant_id
    ).group_by(AuditLog.action)
    
    results = await db.execute(query)
    action_counts = {row[0]: row[1] for row in results}
    
    # Total logs
    total = await db.scalar(
        select(func.count(AuditLog.id)).where(AuditLog.tenant_id == tenant_id)
    )
    
    return {
        "total_logs": total or 0,
        "action_summary": action_counts,
    }
