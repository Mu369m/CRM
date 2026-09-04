"""Workflow and automation API endpoints."""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.middleware.audit_logger import AuditLogger
from app.middleware.rbac_enforcer import require_permission
from app.security import current_claims
from app.models import (
    Workflow,
    WorkflowAction,
    WorkflowCondition,
    WorkflowExecution,
    WorkflowActionExecution,
)
from app.tenant import get_tenant_id
from pydantic import BaseModel, Field

router = APIRouter(prefix="/workflows", tags=["workflows"])

# ========== SCHEMAS ==========


class WorkflowActionCreateSchema(BaseModel):
    """Schema for creating workflow actions."""

    action_type: str = Field(
        ...,
        description="Type of action: send_notification, assign_lead, create_task, etc.",
    )
    action_config: dict = Field(
        default_factory=dict, description="Configuration for the action"
    )
    order: int = Field(default=0, description="Execution order")


class WorkflowActionResponseSchema(BaseModel):
    """Schema for workflow action responses."""

    id: UUID
    workflow_id: UUID
    action_type: str
    action_config: dict
    order: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class WorkflowConditionCreateSchema(BaseModel):
    """Schema for creating workflow conditions."""

    field_name: str = Field(..., description="Field to evaluate")
    operator: str = Field(
        ..., description="Comparison operator: equals, contains, greater_than, etc."
    )
    value: Optional[str] = Field(None, description="Value to compare against")
    logic_operator: str = Field(default="AND", description="Logic operator: AND or OR")


class WorkflowConditionResponseSchema(BaseModel):
    """Schema for workflow condition responses."""

    id: UUID
    workflow_id: UUID
    field_name: str
    operator: str
    value: Optional[str]
    logic_operator: str
    order: int
    created_at: datetime

    class Config:
        from_attributes = True


class WorkflowCreateSchema(BaseModel):
    """Schema for creating workflows."""

    name: str = Field(..., min_length=1, max_length=200, description="Workflow name")
    description: Optional[str] = Field(None, description="Workflow description")
    entity_type: str = Field(
        ..., description="Entity type: lead, client, deposit, etc."
    )
    trigger_type: str = Field(
        ..., description="Trigger type: entity_created, status_changed, time_based"
    )
    trigger_config: dict = Field(
        default_factory=dict, description="Trigger configuration"
    )
    actions: Optional[list[WorkflowActionCreateSchema]] = Field(
        None, description="Initial actions"
    )
    conditions: Optional[list[WorkflowConditionCreateSchema]] = Field(
        None, description="Initial conditions"
    )


class WorkflowUpdateSchema(BaseModel):
    """Schema for updating workflows."""

    name: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = None
    trigger_type: Optional[str] = None
    trigger_config: Optional[dict] = None
    is_active: Optional[bool] = None


class WorkflowResponseSchema(BaseModel):
    """Schema for workflow responses."""

    id: UUID
    tenant_id: UUID
    name: str
    description: Optional[str]
    entity_type: str
    is_active: bool
    trigger_type: str
    trigger_config: dict
    created_by: UUID
    actions: list[WorkflowActionResponseSchema] = Field(default_factory=list)
    conditions: list[WorkflowConditionResponseSchema] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class WorkflowExecutionResponseSchema(BaseModel):
    """Schema for workflow execution responses."""

    id: UUID
    workflow_id: UUID
    entity_id: UUID
    entity_type: str
    status: str
    error_message: Optional[str]
    execution_data: dict
    started_at: datetime
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True


# ========== ENDPOINTS ==========


@router.post("", response_model=WorkflowResponseSchema, status_code=201)
async def create_workflow(
    payload: WorkflowCreateSchema,
    db: AsyncSession = Depends(get_db),
    tenant_id: UUID = Depends(get_tenant_id),
    claims: dict[str, str] = Depends(current_claims),
    _=Depends(require_permission("workflows.create")),
) -> WorkflowResponseSchema:
    """Create a new workflow."""
    try:
        # Check if name is unique
        existing = await db.execute(
            select(Workflow).where(
                and_(Workflow.tenant_id == tenant_id, Workflow.name == payload.name)
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="Workflow name already exists")

        workflow = Workflow(
            tenant_id=tenant_id,
            name=payload.name,
            description=payload.description,
            entity_type=payload.entity_type,
            trigger_type=payload.trigger_type,
            trigger_config=payload.trigger_config,
            created_by=UUID(claims["sub"]),
        )
        db.add(workflow)
        await db.flush()

        # Add actions
        if payload.actions:
            for action in payload.actions:
                db.add(
                    WorkflowAction(
                        workflow_id=workflow.id,
                        action_type=action.action_type,
                        action_config=action.action_config,
                        order=action.order,
                    )
                )

        # Add conditions
        if payload.conditions:
            for idx, condition in enumerate(payload.conditions):
                db.add(
                    WorkflowCondition(
                        workflow_id=workflow.id,
                        field_name=condition.field_name,
                        operator=condition.operator,
                        value=condition.value,
                        logic_operator=condition.logic_operator,
                        order=idx,
                    )
                )

        await db.commit()
        await db.refresh(workflow)
        await AuditLogger.log_create(
            db, tenant_id, "Workflow", workflow.id, {"name": workflow.name}
        )
        return WorkflowResponseSchema.model_validate(workflow)
    except HTTPException:
        raise
    except Exception:
        await db.rollback()
        raise HTTPException(status_code=500, detail="Unable to create workflow")


@router.get("", response_model=list[WorkflowResponseSchema])
async def list_workflows(
    db: AsyncSession = Depends(get_db),
    tenant_id: UUID = Depends(get_tenant_id),
    entity_type: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    _=Depends(require_permission("workflows.view")),
) -> list[WorkflowResponseSchema]:
    """List workflows with optional filters."""
    query = select(Workflow).where(Workflow.tenant_id == tenant_id)

    if entity_type:
        query = query.where(Workflow.entity_type == entity_type)
    if is_active is not None:
        query = query.where(Workflow.is_active == is_active)

    query = query.order_by(desc(Workflow.created_at)).limit(limit).offset(offset)
    result = await db.execute(query)
    workflows = result.scalars().all()

    return [WorkflowResponseSchema.model_validate(w) for w in workflows]


@router.get("/{workflow_id}", response_model=WorkflowResponseSchema)
async def get_workflow(
    workflow_id: UUID,
    db: AsyncSession = Depends(get_db),
    tenant_id: UUID = Depends(get_tenant_id),
    _=Depends(require_permission("workflows.view")),
) -> WorkflowResponseSchema:
    """Get workflow details."""
    workflow = await db.execute(
        select(Workflow).where(
            and_(Workflow.id == workflow_id, Workflow.tenant_id == tenant_id)
        )
    )
    wf = workflow.scalar_one_or_none()
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return WorkflowResponseSchema.model_validate(wf)


@router.put("/{workflow_id}", response_model=WorkflowResponseSchema)
async def update_workflow(
    workflow_id: UUID,
    payload: WorkflowUpdateSchema,
    db: AsyncSession = Depends(get_db),
    tenant_id: UUID = Depends(get_tenant_id),
    _=Depends(require_permission("workflows.edit")),
) -> WorkflowResponseSchema:
    """Update a workflow."""
    workflow = await db.execute(
        select(Workflow).where(
            and_(Workflow.id == workflow_id, Workflow.tenant_id == tenant_id)
        )
    )
    wf = workflow.scalar_one_or_none()
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(wf, field, value)

    await db.commit()
    await AuditLogger.log_update(db, tenant_id, "Workflow", workflow_id, update_data)
    await db.refresh(wf)
    return WorkflowResponseSchema.model_validate(wf)


@router.delete("/{workflow_id}", status_code=204)
async def delete_workflow(
    workflow_id: UUID,
    db: AsyncSession = Depends(get_db),
    tenant_id: UUID = Depends(get_tenant_id),
    _=Depends(require_permission("workflows.delete")),
):
    """Delete a workflow."""
    workflow = await db.execute(
        select(Workflow).where(
            and_(Workflow.id == workflow_id, Workflow.tenant_id == tenant_id)
        )
    )
    wf = workflow.scalar_one_or_none()
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")

    await db.delete(wf)
    await db.commit()
    await AuditLogger.log_delete(db, tenant_id, "Workflow", workflow_id)


# ========== WORKFLOW ACTIONS ENDPOINTS ==========


@router.post(
    "/{workflow_id}/actions",
    response_model=WorkflowActionResponseSchema,
    status_code=201,
)
async def create_workflow_action(
    workflow_id: UUID,
    payload: WorkflowActionCreateSchema,
    db: AsyncSession = Depends(get_db),
    tenant_id: UUID = Depends(get_tenant_id),
    _=Depends(require_permission("workflows.edit")),
) -> WorkflowActionResponseSchema:
    """Add an action to a workflow."""
    # Verify workflow exists
    workflow = await db.execute(
        select(Workflow).where(
            and_(Workflow.id == workflow_id, Workflow.tenant_id == tenant_id)
        )
    )
    if not workflow.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Workflow not found")

    action = WorkflowAction(
        workflow_id=workflow_id,
        action_type=payload.action_type,
        action_config=payload.action_config,
        order=payload.order,
    )
    db.add(action)
    await db.commit()
    await db.refresh(action)
    return WorkflowActionResponseSchema.model_validate(action)


@router.put(
    "/{workflow_id}/actions/{action_id}", response_model=WorkflowActionResponseSchema
)
async def update_workflow_action(
    workflow_id: UUID,
    action_id: UUID,
    payload: WorkflowActionCreateSchema,
    db: AsyncSession = Depends(get_db),
    tenant_id: UUID = Depends(get_tenant_id),
    _=Depends(require_permission("workflows.edit")),
) -> WorkflowActionResponseSchema:
    """Update a workflow action."""
    workflow = await db.scalar(
        select(Workflow).where(
            Workflow.id == workflow_id, Workflow.tenant_id == tenant_id
        )
    )
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    action = await db.execute(
        select(WorkflowAction).where(
            and_(
                WorkflowAction.id == action_id,
                WorkflowAction.workflow_id == workflow_id,
            )
        )
    )
    act = action.scalar_one_or_none()
    if not act:
        raise HTTPException(status_code=404, detail="Action not found")

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(act, field, value)

    await db.commit()
    await db.refresh(act)
    return WorkflowActionResponseSchema.model_validate(act)


@router.delete("/{workflow_id}/actions/{action_id}", status_code=204)
async def delete_workflow_action(
    workflow_id: UUID,
    action_id: UUID,
    db: AsyncSession = Depends(get_db),
    tenant_id: UUID = Depends(get_tenant_id),
    _=Depends(require_permission("workflows.edit")),
):
    """Delete a workflow action."""
    workflow = await db.scalar(
        select(Workflow).where(
            Workflow.id == workflow_id, Workflow.tenant_id == tenant_id
        )
    )
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    action = await db.execute(
        select(WorkflowAction).where(
            and_(
                WorkflowAction.id == action_id,
                WorkflowAction.workflow_id == workflow_id,
            )
        )
    )
    act = action.scalar_one_or_none()
    if not act:
        raise HTTPException(status_code=404, detail="Action not found")

    await db.delete(act)
    await db.commit()


# ========== WORKFLOW CONDITIONS ENDPOINTS ==========


@router.post(
    "/{workflow_id}/conditions",
    response_model=WorkflowConditionResponseSchema,
    status_code=201,
)
async def create_workflow_condition(
    workflow_id: UUID,
    payload: WorkflowConditionCreateSchema,
    db: AsyncSession = Depends(get_db),
    tenant_id: UUID = Depends(get_tenant_id),
    _=Depends(require_permission("workflows.edit")),
) -> WorkflowConditionResponseSchema:
    """Add a condition to a workflow."""
    # Verify workflow exists
    workflow = await db.execute(
        select(Workflow).where(
            and_(Workflow.id == workflow_id, Workflow.tenant_id == tenant_id)
        )
    )
    if not workflow.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Workflow not found")

    condition = WorkflowCondition(
        workflow_id=workflow_id,
        field_name=payload.field_name,
        operator=payload.operator,
        value=payload.value,
        logic_operator=payload.logic_operator,
    )
    db.add(condition)
    await db.commit()
    await db.refresh(condition)
    return WorkflowConditionResponseSchema.model_validate(condition)


@router.delete("/{workflow_id}/conditions/{condition_id}", status_code=204)
async def delete_workflow_condition(
    workflow_id: UUID,
    condition_id: UUID,
    db: AsyncSession = Depends(get_db),
    tenant_id: UUID = Depends(get_tenant_id),
    _=Depends(require_permission("workflows.edit")),
):
    """Delete a workflow condition."""
    workflow = await db.scalar(
        select(Workflow).where(
            Workflow.id == workflow_id, Workflow.tenant_id == tenant_id
        )
    )
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    condition = await db.execute(
        select(WorkflowCondition).where(
            and_(
                WorkflowCondition.id == condition_id,
                WorkflowCondition.workflow_id == workflow_id,
            )
        )
    )
    cond = condition.scalar_one_or_none()
    if not cond:
        raise HTTPException(status_code=404, detail="Condition not found")

    await db.delete(cond)
    await db.commit()


# ========== WORKFLOW EXECUTIONS ENDPOINTS ==========


@router.get(
    "/{workflow_id}/executions", response_model=list[WorkflowExecutionResponseSchema]
)
async def list_workflow_executions(
    workflow_id: UUID,
    db: AsyncSession = Depends(get_db),
    tenant_id: UUID = Depends(get_tenant_id),
    status: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    _=Depends(require_permission("workflows.view")),
) -> list[WorkflowExecutionResponseSchema]:
    """List workflow executions."""
    query = select(WorkflowExecution).where(
        and_(
            WorkflowExecution.workflow_id == workflow_id,
            WorkflowExecution.tenant_id == tenant_id,
        )
    )

    if status:
        query = query.where(WorkflowExecution.status == status)

    query = (
        query.order_by(desc(WorkflowExecution.started_at)).limit(limit).offset(offset)
    )
    result = await db.execute(query)
    executions = result.scalars().all()

    return [WorkflowExecutionResponseSchema.model_validate(e) for e in executions]


@router.get(
    "/{workflow_id}/executions/{execution_id}",
    response_model=WorkflowExecutionResponseSchema,
)
async def get_workflow_execution(
    workflow_id: UUID,
    execution_id: UUID,
    db: AsyncSession = Depends(get_db),
    tenant_id: UUID = Depends(get_tenant_id),
    _=Depends(require_permission("workflows.view")),
) -> WorkflowExecutionResponseSchema:
    """Get workflow execution details."""
    execution = await db.execute(
        select(WorkflowExecution).where(
            and_(
                WorkflowExecution.id == execution_id,
                WorkflowExecution.workflow_id == workflow_id,
                WorkflowExecution.tenant_id == tenant_id,
            )
        )
    )
    exec_obj = execution.scalar_one_or_none()
    if not exec_obj:
        raise HTTPException(status_code=404, detail="Execution not found")
    return WorkflowExecutionResponseSchema.model_validate(exec_obj)
