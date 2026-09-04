"""Pipeline management API for broker customization."""

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from app.core.db_router import get_tenant_db
from app.models import Pipeline, PipelineStage
from app.security import current_claims

router = APIRouter(prefix="/api/v1/broker/pipelines", tags=["Pipelines"])


# ===== Pydantic Schemas =====
class PipelineStageCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    color: str = Field(default="#6B7280", pattern="^#[0-9A-Fa-f]{6}$")
    display_order: int = 0
    required_fields: List[str] = Field(default_factory=list)
    is_terminal: bool = False


class PipelineStageUpdate(BaseModel):
    name: str | None = None
    color: str | None = None
    display_order: int | None = None
    required_fields: List[str] | None = None
    is_terminal: bool | None = None


class PipelineStageResponse(BaseModel):
    id: UUID
    name: str
    color: str
    display_order: int
    required_fields: List[str]
    is_terminal: bool
    created_at: str

    class Config:
        from_attributes = True


class PipelineCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    entity_type: str = Field(..., pattern="^(LEAD|CLIENT|IB|ACCOUNT)$")
    description: str | None = None
    is_default: bool = False


class PipelineUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    is_active: bool | None = None
    is_default: bool | None = None


class PipelineResponse(BaseModel):
    id: UUID
    name: str
    entity_type: str
    description: str | None
    is_active: bool
    is_default: bool
    created_at: str
    stages: List[PipelineStageResponse] = []

    class Config:
        from_attributes = True


# ===== Endpoints =====
@router.post("", response_model=PipelineResponse, status_code=status.HTTP_201_CREATED)
async def create_pipeline(
    payload: PipelineCreate,
    claims: dict = Depends(current_claims),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Create a new pipeline."""
    tenant_id = UUID(claims["tenant_id"])

    # Verify pipeline name is unique per tenant
    result = await db.execute(
        select(Pipeline).where(
            (Pipeline.tenant_id == tenant_id) & (Pipeline.name == payload.name)
        )
    )
    if result.scalar():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Pipeline name already exists"
        )

    # If marking as default, unset other defaults for this entity type
    if payload.is_default:
        await db.execute(
            select(Pipeline).where(
                (Pipeline.tenant_id == tenant_id)
                & (Pipeline.entity_type == payload.entity_type)
                & (Pipeline.is_default == True)
            )
        )
        # Update would happen here if needed

    pipeline = Pipeline(
        tenant_id=tenant_id,
        name=payload.name,
        entity_type=payload.entity_type,
        description=payload.description,
        is_default=payload.is_default,
    )
    db.add(pipeline)
    await db.commit()
    await db.refresh(pipeline)
    return pipeline


@router.get("", response_model=List[PipelineResponse])
async def list_pipelines(
    entity_type: str | None = Query(None),
    claims: dict = Depends(current_claims),
    db: AsyncSession = Depends(get_tenant_db),
):
    """List all pipelines for a tenant."""
    tenant_id = UUID(claims["tenant_id"])

    query = select(Pipeline).where(Pipeline.tenant_id == tenant_id)

    if entity_type:
        query = query.where(Pipeline.entity_type == entity_type)

    query = query.order_by(Pipeline.name)
    result = await db.execute(query)
    pipelines = result.scalars().all()
    return pipelines


@router.get("/{pipeline_id}", response_model=PipelineResponse)
async def get_pipeline(
    pipeline_id: UUID,
    claims: dict = Depends(current_claims),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Get a specific pipeline."""
    tenant_id = UUID(claims["tenant_id"])

    result = await db.execute(
        select(Pipeline).where(
            (Pipeline.id == pipeline_id) & (Pipeline.tenant_id == tenant_id)
        )
    )
    pipeline = result.scalar()

    if not pipeline:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    return pipeline


@router.put("/{pipeline_id}", response_model=PipelineResponse)
async def update_pipeline(
    pipeline_id: UUID,
    payload: PipelineUpdate,
    claims: dict = Depends(current_claims),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Update a pipeline."""
    tenant_id = UUID(claims["tenant_id"])

    result = await db.execute(
        select(Pipeline).where(
            (Pipeline.id == pipeline_id) & (Pipeline.tenant_id == tenant_id)
        )
    )
    pipeline = result.scalar()

    if not pipeline:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    # Update fields
    update_data = payload.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(pipeline, key, value)

    await db.commit()
    await db.refresh(pipeline)
    return pipeline


@router.delete("/{pipeline_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_pipeline(
    pipeline_id: UUID,
    claims: dict = Depends(current_claims),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Delete a pipeline."""
    tenant_id = UUID(claims["tenant_id"])

    result = await db.execute(
        select(Pipeline).where(
            (Pipeline.id == pipeline_id) & (Pipeline.tenant_id == tenant_id)
        )
    )
    pipeline = result.scalar()

    if not pipeline:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    await db.delete(pipeline)
    await db.commit()


# ===== Pipeline Stages =====
@router.post(
    "/{pipeline_id}/stages",
    response_model=PipelineStageResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_stage(
    pipeline_id: UUID,
    payload: PipelineStageCreate,
    claims: dict = Depends(current_claims),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Add a stage to a pipeline."""
    tenant_id = UUID(claims["tenant_id"])

    # Verify pipeline exists
    result = await db.execute(
        select(Pipeline).where(
            (Pipeline.id == pipeline_id) & (Pipeline.tenant_id == tenant_id)
        )
    )
    if not result.scalar():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Pipeline not found"
        )

    # Verify stage name is unique within pipeline
    result = await db.execute(
        select(PipelineStage).where(
            (PipelineStage.pipeline_id == pipeline_id)
            & (PipelineStage.name == payload.name)
        )
    )
    if result.scalar():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Stage name already exists in pipeline",
        )

    stage = PipelineStage(
        pipeline_id=pipeline_id,
        name=payload.name,
        color=payload.color,
        display_order=payload.display_order,
        required_fields=payload.required_fields,
        is_terminal=payload.is_terminal,
    )
    db.add(stage)
    await db.commit()
    await db.refresh(stage)
    return stage


@router.get("/{pipeline_id}/stages", response_model=List[PipelineStageResponse])
async def list_stages(
    pipeline_id: UUID,
    claims: dict = Depends(current_claims),
    db: AsyncSession = Depends(get_tenant_db),
):
    """List all stages in a pipeline."""
    tenant_id = UUID(claims["tenant_id"])

    # Verify pipeline belongs to tenant
    result = await db.execute(
        select(Pipeline).where(
            (Pipeline.id == pipeline_id) & (Pipeline.tenant_id == tenant_id)
        )
    )
    if not result.scalar():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    result = await db.execute(
        select(PipelineStage)
        .where(PipelineStage.pipeline_id == pipeline_id)
        .order_by(PipelineStage.display_order)
    )
    stages = result.scalars().all()
    return stages


@router.get("/stages/{stage_id}", response_model=PipelineStageResponse)
async def get_stage(
    stage_id: UUID,
    claims: dict = Depends(current_claims),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Get a specific stage."""
    result = await db.execute(select(PipelineStage).where(PipelineStage.id == stage_id))
    stage = result.scalar()

    if not stage:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    # Verify pipeline belongs to tenant
    tenant_id = UUID(claims["tenant_id"])
    result = await db.execute(
        select(Pipeline).where(
            (Pipeline.id == stage.pipeline_id) & (Pipeline.tenant_id == tenant_id)
        )
    )
    if not result.scalar():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    return stage


@router.put("/stages/{stage_id}", response_model=PipelineStageResponse)
async def update_stage(
    stage_id: UUID,
    payload: PipelineStageUpdate,
    claims: dict = Depends(current_claims),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Update a stage."""
    tenant_id = UUID(claims["tenant_id"])

    result = await db.execute(select(PipelineStage).where(PipelineStage.id == stage_id))
    stage = result.scalar()

    if not stage:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    # Verify pipeline belongs to tenant
    result = await db.execute(
        select(Pipeline).where(
            (Pipeline.id == stage.pipeline_id) & (Pipeline.tenant_id == tenant_id)
        )
    )
    if not result.scalar():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    # Update fields
    update_data = payload.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(stage, key, value)

    await db.commit()
    await db.refresh(stage)
    return stage


@router.delete("/stages/{stage_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_stage(
    stage_id: UUID,
    claims: dict = Depends(current_claims),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Delete a stage."""
    tenant_id = UUID(claims["tenant_id"])

    result = await db.execute(select(PipelineStage).where(PipelineStage.id == stage_id))
    stage = result.scalar()

    if not stage:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    # Verify pipeline belongs to tenant
    result = await db.execute(
        select(Pipeline).where(
            (Pipeline.id == stage.pipeline_id) & (Pipeline.tenant_id == tenant_id)
        )
    )
    if not result.scalar():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    await db.delete(stage)
    await db.commit()
