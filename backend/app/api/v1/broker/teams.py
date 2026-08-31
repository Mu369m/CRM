"""
Team management API endpoints.

Allows brokers to organize users into teams and manage team membership.
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
from app.models import Team, TeamMember, User, Department
from app.middleware.permission_check import check_permission

router = APIRouter(prefix="/teams", tags=["teams"])


# ========== Schemas ==========

class TeamCreate(BaseModel):
    name: str
    department_id: UUID
    description: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "name": "Sales Team A",
                "department_id": "550e8400-e29b-41d4-a716-446655440000",
                "description": "Europe sales team"
            }
        }


class TeamUpdate(BaseModel):
    name: Optional[str] = None
    department_id: Optional[UUID] = None
    description: Optional[str] = None


class TeamMemberCreate(BaseModel):
    user_id: UUID
    role: str = "member"  # member, lead, manager

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "550e8400-e29b-41d4-a716-446655440000",
                "role": "member"
            }
        }


class TeamMemberResponse(BaseModel):
    id: UUID
    team_id: UUID
    user_id: UUID
    role: str
    joined_at: datetime

    class Config:
        from_attributes = True


class TeamResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    department_id: UUID
    name: str
    description: Optional[str]
    member_count: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TeamResponseWithMembers(TeamResponse):
    members: List[TeamMemberResponse]


# ========== Endpoints ==========

@router.post("/", response_model=TeamResponse, status_code=status.HTTP_201_CREATED)
async def create_team(
    payload: TeamCreate,
    claims: dict = Depends(current_claims),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Create a new team"""
    
    tenant_id = UUID(claims["tenant_id"])
    
    # Check permission
    has_permission = await check_permission(
        UUID(claims["sub"]), "settings", "manage", db, tenant_id
    )
    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    
    # Verify department exists
    result = await db.execute(
        select(Department).where(
            (Department.id == payload.department_id)
            & (Department.tenant_id == tenant_id)
        )
    )
    if not result.scalar():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Department not found"
        )
    
    team = Team(
        tenant_id=tenant_id,
        department_id=payload.department_id,
        name=payload.name,
        description=payload.description,
    )
    
    db.add(team)
    await db.commit()
    await db.refresh(team)
    
    return team


@router.get("/", response_model=List[TeamResponse])
async def list_teams(
    dept_id: Optional[UUID] = None,
    claims: dict = Depends(current_claims),
    db: AsyncSession = Depends(get_tenant_db),
):
    """List teams, optionally filter by department"""
    
    tenant_id = UUID(claims["tenant_id"])
    
    query = select(Team).where(Team.tenant_id == tenant_id)
    
    if dept_id:
        query = query.where(Team.department_id == dept_id)
    
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{team_id}", response_model=TeamResponseWithMembers)
async def get_team(
    team_id: UUID,
    claims: dict = Depends(current_claims),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Get team with members"""
    
    tenant_id = UUID(claims["tenant_id"])
    
    result = await db.execute(
        select(Team).where(
            (Team.id == team_id) & (Team.tenant_id == tenant_id)
        )
    )
    team = result.scalar()
    
    if not team:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    
    # Get members
    result = await db.execute(
        select(TeamMember).where(TeamMember.team_id == team_id)
    )
    members = result.scalars().all()
    
    response = TeamResponseWithMembers(
        **{**team.__dict__, "members": members}
    )
    return response


@router.put("/{team_id}", response_model=TeamResponse)
async def update_team(
    team_id: UUID,
    payload: TeamUpdate,
    claims: dict = Depends(current_claims),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Update team"""
    
    tenant_id = UUID(claims["tenant_id"])
    
    # Check permission
    has_permission = await check_permission(
        UUID(claims["sub"]), "settings", "manage", db, tenant_id
    )
    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    
    result = await db.execute(
        select(Team).where(
            (Team.id == team_id) & (Team.tenant_id == tenant_id)
        )
    )
    team = result.scalar()
    
    if not team:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    
    update_data = payload.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(team, key, value)
    
    team.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(team)
    
    return team


@router.delete("/{team_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_team(
    team_id: UUID,
    claims: dict = Depends(current_claims),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Delete team"""
    
    tenant_id = UUID(claims["tenant_id"])
    
    # Check permission
    has_permission = await check_permission(
        UUID(claims["sub"]), "settings", "manage", db, tenant_id
    )
    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    
    result = await db.execute(
        select(Team).where(
            (Team.id == team_id) & (Team.tenant_id == tenant_id)
        )
    )
    team = result.scalar()
    
    if not team:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    
    await db.delete(team)
    await db.commit()


# ========== Team Members ==========

@router.post("/{team_id}/members", response_model=TeamMemberResponse)
async def add_team_member(
    team_id: UUID,
    payload: TeamMemberCreate,
    claims: dict = Depends(current_claims),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Add member to team"""
    
    tenant_id = UUID(claims["tenant_id"])
    
    # Check permission
    has_permission = await check_permission(
        UUID(claims["sub"]), "settings", "manage", db, tenant_id
    )
    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    
    # Verify team exists
    result = await db.execute(
        select(Team).where(
            (Team.id == team_id) & (Team.tenant_id == tenant_id)
        )
    )
    if not result.scalar():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")
    
    # Verify user exists and belongs to tenant
    result = await db.execute(
        select(User).where(
            (User.id == payload.user_id) & (User.tenant_id == tenant_id)
        )
    )
    if not result.scalar():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    # Check if already member
    result = await db.execute(
        select(TeamMember).where(
            (TeamMember.team_id == team_id) & (TeamMember.user_id == payload.user_id)
        )
    )
    if result.scalar():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User already member of team"
        )
    
    member = TeamMember(
        tenant_id=tenant_id,
        team_id=team_id,
        user_id=payload.user_id,
        role=payload.role,
    )
    
    db.add(member)
    await db.commit()
    await db.refresh(member)
    
    return member


@router.delete("/{team_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_team_member(
    team_id: UUID,
    user_id: UUID,
    claims: dict = Depends(current_claims),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Remove member from team"""
    
    tenant_id = UUID(claims["tenant_id"])
    
    # Check permission
    has_permission = await check_permission(
        UUID(claims["sub"]), "settings", "manage", db, tenant_id
    )
    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    
    result = await db.execute(
        select(TeamMember).where(
            (TeamMember.team_id == team_id)
            & (TeamMember.user_id == user_id)
            & (TeamMember.tenant_id == tenant_id)
        )
    )
    member = result.scalar()
    
    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    
    await db.delete(member)
    await db.commit()
