"""
Department management API endpoints.

Allows brokers to organize users into departments.
"""

from uuid import UUID
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.db import get_tenant_db
from app.security import current_claims
from app.models import Department, Team
from app.middleware.permission_check import check_permission

router = APIRouter(prefix="/departments", tags=["departments"])


# ========== Schemas ==========

class DepartmentCreate(BaseModel):
    name: str
    description: Optional[str] = None
    manager_id: Optional[UUID] = None

    class Config:
        json_schema_extra = {
            "example": {
                "name": "Sales Department",
                "description": "Sales team",
                "manager_id": "550e8400-e29b-41d4-a716-446655440000"
            }
        }


class DepartmentUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    manager_id: Optional[UUID] = None

    class Config:
        json_schema_extra = {
            "example": {
                "name": "Sales - Updated",
                "manager_id": None
            }
        }


class DepartmentResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str
    description: Optional[str]
    manager_id: Optional[UUID]
    team_count: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ========== Endpoints ==========

@router.post("/", response_model=DepartmentResponse, status_code=status.HTTP_201_CREATED)
async def create_department(
    payload: DepartmentCreate,
    claims: dict = Depends(current_claims),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Create a new department. Requires: settings.manage"""
    
    tenant_id = UUID(claims["tenant_id"])
    
    # Check permission
    has_permission = await check_permission(
        UUID(claims["sub"]), "settings", "manage", db, tenant_id
    )
    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    
    department = Department(
        tenant_id=tenant_id,
        name=payload.name,
        description=payload.description,
        manager_id=payload.manager_id,
    )
    
    db.add(department)
    await db.commit()
    await db.refresh(department)
    
    return department


@router.get("/", response_model=List[DepartmentResponse])
async def list_departments(
    claims: dict = Depends(current_claims),
    db: AsyncSession = Depends(get_tenant_db),
):
    """List all departments for tenant"""
    
    tenant_id = UUID(claims["tenant_id"])
    
    result = await db.execute(
        select(Department).where(Department.tenant_id == tenant_id)
    )
    departments = result.scalars().all()
    
    return departments


@router.get("/{dept_id}", response_model=DepartmentResponse)
async def get_department(
    dept_id: UUID,
    claims: dict = Depends(current_claims),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Get department details with team count"""
    
    tenant_id = UUID(claims["tenant_id"])
    
    result = await db.execute(
        select(Department).where(
            (Department.id == dept_id) & (Department.tenant_id == tenant_id)
        )
    )
    department = result.scalar()
    
    if not department:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    
    return department


@router.put("/{dept_id}", response_model=DepartmentResponse)
async def update_department(
    dept_id: UUID,
    payload: DepartmentUpdate,
    claims: dict = Depends(current_claims),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Update department. Requires: settings.manage"""
    
    tenant_id = UUID(claims["tenant_id"])
    
    # Check permission
    has_permission = await check_permission(
        UUID(claims["sub"]), "settings", "manage", db, tenant_id
    )
    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    
    result = await db.execute(
        select(Department).where(
            (Department.id == dept_id) & (Department.tenant_id == tenant_id)
        )
    )
    department = result.scalar()
    
    if not department:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    
    update_data = payload.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(department, key, value)
    
    department.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(department)
    
    return department


@router.delete("/{dept_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_department(
    dept_id: UUID,
    claims: dict = Depends(current_claims),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Delete department. Requires: settings.manage"""
    
    tenant_id = UUID(claims["tenant_id"])
    
    # Check permission
    has_permission = await check_permission(
        UUID(claims["sub"]), "settings", "manage", db, tenant_id
    )
    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    
    result = await db.execute(
        select(Department).where(
            (Department.id == dept_id) & (Department.tenant_id == tenant_id)
        )
    )
    department = result.scalar()
    
    if not department:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    
    await db.delete(department)
    await db.commit()
