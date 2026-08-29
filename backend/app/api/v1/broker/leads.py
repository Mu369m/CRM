"""Lead management API."""

from datetime import datetime
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, desc, and_
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field, EmailStr

from app.core.db_router import get_tenant_db
from app.models import Lead, Task, Note, Activity, Pipeline, PipelineStage
from app.security import current_claims

router = APIRouter(prefix="/api/v1/broker/leads", tags=["Leads"])


# ===== Pydantic Schemas =====
class LeadCreate(BaseModel):
    email: EmailStr
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    phone: str | None = None
    country: str | None = Field(None, max_length=2)
    source: str | None = None
    campaign_id: UUID | None = None
    pipeline_id: UUID
    stage_id: UUID
    notes: str | None = None


class LeadUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    country: str | None = None
    source: str | None = None
    campaign_id: UUID | None = None
    assigned_to_id: UUID | None = None
    stage_id: UUID | None = None
    lead_score: int | None = None
    notes: str | None = None
    next_followup_at: datetime | None = None


class LeadResponse(BaseModel):
    id: UUID
    email: str
    first_name: str
    last_name: str
    phone: str | None
    country: str | None
    source: str | None
    campaign_id: UUID | None
    assigned_to_id: UUID | None
    pipeline_id: UUID
    stage_id: UUID
    lead_score: int
    notes: str | None
    last_contact_at: datetime | None
    next_followup_at: datetime | None
    is_archived: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class LeadListResponse(BaseModel):
    id: UUID
    email: str
    first_name: str
    last_name: str
    source: str | None
    lead_score: int
    assigned_to_id: UUID | None
    stage_id: UUID
    last_contact_at: datetime | None
    next_followup_at: datetime | None
    created_at: datetime

    class Config:
        from_attributes = True


class LeadPageResponse(BaseModel):
    total: int
    page: int
    limit: int
    items: List[LeadListResponse]


class TaskCreate(BaseModel):
    entity_type: str = "LEAD"
    title: str = Field(..., min_length=1, max_length=200)
    description: str | None = None
    assigned_to_id: UUID
    priority: str = Field(default="NORMAL", regex="^(LOW|NORMAL|HIGH|URGENT)$")
    due_date: datetime | None = None


class TaskResponse(BaseModel):
    id: UUID
    entity_type: str
    entity_id: UUID
    title: str
    description: str | None
    assigned_to_id: UUID
    priority: str
    status: str
    due_date: datetime | None
    completed_at: datetime | None
    created_at: datetime

    class Config:
        from_attributes = True


class NoteCreate(BaseModel):
    content: str = Field(..., min_length=1)


class NoteResponse(BaseModel):
    id: UUID
    content: str
    user_id: UUID | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ActivityResponse(BaseModel):
    id: UUID
    activity_type: str
    description: str
    user_id: UUID | None
    created_at: datetime

    class Config:
        from_attributes = True


# ===== Endpoints =====
@router.post("", response_model=LeadResponse, status_code=status.HTTP_201_CREATED)
async def create_lead(
    payload: LeadCreate,
    claims: dict = Depends(current_claims),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Create a new lead."""
    tenant_id = UUID(claims["tenant_id"])
    user_id = UUID(claims["sub"])
    
    # Verify pipeline and stage exist and belong to tenant
    result = await db.execute(
        select(Pipeline).where(
            (Pipeline.id == payload.pipeline_id)
            & (Pipeline.tenant_id == tenant_id)
        )
    )
    if not result.scalar():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pipeline not found")
    
    result = await db.execute(
        select(PipelineStage).where(
            (PipelineStage.id == payload.stage_id)
            & (PipelineStage.pipeline_id == payload.pipeline_id)
        )
    )
    if not result.scalar():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stage not found")
    
    lead = Lead(
        tenant_id=tenant_id,
        email=payload.email,
        first_name=payload.first_name,
        last_name=payload.last_name,
        phone=payload.phone,
        country=payload.country,
        source=payload.source,
        campaign_id=payload.campaign_id,
        pipeline_id=payload.pipeline_id,
        stage_id=payload.stage_id,
        notes=payload.notes,
    )
    db.add(lead)
    await db.commit()
    await db.refresh(lead)
    
    # Log activity
    activity = Activity(
        tenant_id=tenant_id,
        entity_type="LEAD",
        entity_id=lead.id,
        activity_type="CREATED",
        description=f"Lead created: {payload.first_name} {payload.last_name}",
        user_id=user_id,
    )
    db.add(activity)
    await db.commit()
    
    return lead


@router.get("", response_model=LeadPageResponse)
async def list_leads(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: str | None = Query(None),
    source: str | None = Query(None),
    stage_id: UUID | None = Query(None),
    assigned_to_id: UUID | None = Query(None),
    is_archived: bool = Query(False),
    claims: dict = Depends(current_claims),
    db: AsyncSession = Depends(get_tenant_db),
):
    """List leads with filtering."""
    tenant_id = UUID(claims["tenant_id"])
    
    query = select(Lead).where(
        (Lead.tenant_id == tenant_id)
        & (Lead.is_archived == is_archived)
    )
    
    if search:
        search_term = f"%{search}%"
        query = query.where(
            (Lead.email.ilike(search_term))
            | (Lead.first_name.ilike(search_term))
            | (Lead.last_name.ilike(search_term))
            | (Lead.phone.ilike(search_term))
        )
    
    if source:
        query = query.where(Lead.source == source)
    
    if stage_id:
        query = query.where(Lead.stage_id == stage_id)
    
    if assigned_to_id:
        query = query.where(Lead.assigned_to_id == assigned_to_id)
    
    # Count total
    count_result = await db.execute(select(Lead).select_entity_from(query))
    total = len(count_result.scalars().all())
    
    # Paginate
    offset = (page - 1) * limit
    query = query.order_by(desc(Lead.created_at)).offset(offset).limit(limit)
    
    result = await db.execute(query)
    leads = result.scalars().all()
    
    return {
        "total": total,
        "page": page,
        "limit": limit,
        "items": leads,
    }


@router.get("/{lead_id}", response_model=LeadResponse)
async def get_lead(
    lead_id: UUID,
    claims: dict = Depends(current_claims),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Get a specific lead."""
    tenant_id = UUID(claims["tenant_id"])
    
    result = await db.execute(
        select(Lead).where(
            (Lead.id == lead_id)
            & (Lead.tenant_id == tenant_id)
        )
    )
    lead = result.scalar()
    
    if not lead:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    
    return lead


@router.put("/{lead_id}", response_model=LeadResponse)
async def update_lead(
    lead_id: UUID,
    payload: LeadUpdate,
    claims: dict = Depends(current_claims),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Update a lead."""
    tenant_id = UUID(claims["tenant_id"])
    user_id = UUID(claims["sub"])
    
    result = await db.execute(
        select(Lead).where(
            (Lead.id == lead_id)
            & (Lead.tenant_id == tenant_id)
        )
    )
    lead = result.scalar()
    
    if not lead:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    
    # Track changes for activity log
    changes = []
    
    update_data = payload.dict(exclude_unset=True)
    for key, value in update_data.items():
        old_value = getattr(lead, key)
        if old_value != value:
            changes.append(f"{key}: {old_value} -> {value}")
        setattr(lead, key, value)
    
    lead.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(lead)
    
    # Log activity if there were changes
    if changes:
        activity = Activity(
            tenant_id=tenant_id,
            entity_type="LEAD",
            entity_id=lead.id,
            activity_type="UPDATED",
            description=f"Lead updated: {', '.join(changes)}",
            user_id=user_id,
        )
        db.add(activity)
        await db.commit()
    
    return lead


@router.delete("/{lead_id}", status_code=status.HTTP_204_NO_CONTENT)
async def archive_lead(
    lead_id: UUID,
    claims: dict = Depends(current_claims),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Archive a lead (soft delete)."""
    tenant_id = UUID(claims["tenant_id"])
    user_id = UUID(claims["sub"])
    
    result = await db.execute(
        select(Lead).where(
            (Lead.id == lead_id)
            & (Lead.tenant_id == tenant_id)
        )
    )
    lead = result.scalar()
    
    if not lead:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    
    lead.is_archived = True
    await db.commit()
    
    # Log activity
    activity = Activity(
        tenant_id=tenant_id,
        entity_type="LEAD",
        entity_id=lead.id,
        activity_type="ARCHIVED",
        description="Lead archived",
        user_id=user_id,
    )
    db.add(activity)
    await db.commit()


# ===== Lead Tasks =====
@router.post("/{lead_id}/tasks", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_lead_task(
    lead_id: UUID,
    payload: TaskCreate,
    claims: dict = Depends(current_claims),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Create a task for a lead."""
    tenant_id = UUID(claims["tenant_id"])
    
    # Verify lead exists
    result = await db.execute(
        select(Lead).where(
            (Lead.id == lead_id)
            & (Lead.tenant_id == tenant_id)
        )
    )
    if not result.scalar():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    
    task = Task(
        tenant_id=tenant_id,
        entity_type="LEAD",
        entity_id=lead_id,
        title=payload.title,
        description=payload.description,
        assigned_to_id=payload.assigned_to_id,
        priority=payload.priority,
        due_date=payload.due_date,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task


@router.get("/{lead_id}/tasks", response_model=List[TaskResponse])
async def list_lead_tasks(
    lead_id: UUID,
    status_filter: str | None = Query(None),
    claims: dict = Depends(current_claims),
    db: AsyncSession = Depends(get_tenant_db),
):
    """List tasks for a lead."""
    tenant_id = UUID(claims["tenant_id"])
    
    query = select(Task).where(
        (Task.tenant_id == tenant_id)
        & (Task.entity_type == "LEAD")
        & (Task.entity_id == lead_id)
    )
    
    if status_filter:
        query = query.where(Task.status == status_filter)
    
    query = query.order_by(desc(Task.created_at))
    result = await db.execute(query)
    tasks = result.scalars().all()
    return tasks


# ===== Lead Notes =====
@router.post("/{lead_id}/notes", response_model=NoteResponse, status_code=status.HTTP_201_CREATED)
async def create_lead_note(
    lead_id: UUID,
    payload: NoteCreate,
    claims: dict = Depends(current_claims),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Create a note on a lead."""
    tenant_id = UUID(claims["tenant_id"])
    user_id = UUID(claims["sub"])
    
    # Verify lead exists
    result = await db.execute(
        select(Lead).where(
            (Lead.id == lead_id)
            & (Lead.tenant_id == tenant_id)
        )
    )
    if not result.scalar():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    
    note = Note(
        tenant_id=tenant_id,
        entity_type="LEAD",
        entity_id=lead_id,
        content=payload.content,
        user_id=user_id,
    )
    db.add(note)
    await db.commit()
    await db.refresh(note)
    return note


@router.get("/{lead_id}/notes", response_model=List[NoteResponse])
async def list_lead_notes(
    lead_id: UUID,
    claims: dict = Depends(current_claims),
    db: AsyncSession = Depends(get_tenant_db),
):
    """List notes on a lead."""
    tenant_id = UUID(claims["tenant_id"])
    
    query = select(Note).where(
        (Note.tenant_id == tenant_id)
        & (Note.entity_type == "LEAD")
        & (Note.entity_id == lead_id)
    ).order_by(desc(Note.created_at))
    
    result = await db.execute(query)
    notes = result.scalars().all()
    return notes


# ===== Lead Activities =====
@router.get("/{lead_id}/activities", response_model=List[ActivityResponse])
async def list_lead_activities(
    lead_id: UUID,
    claims: dict = Depends(current_claims),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Get activity timeline for a lead."""
    tenant_id = UUID(claims["tenant_id"])
    
    query = select(Activity).where(
        (Activity.tenant_id == tenant_id)
        & (Activity.entity_type == "LEAD")
        & (Activity.entity_id == lead_id)
    ).order_by(desc(Activity.created_at))
    
    result = await db.execute(query)
    activities = result.scalars().all()
    return activities
