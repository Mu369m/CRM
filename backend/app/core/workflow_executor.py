"""Workflow execution engine for processing workflow automations."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Workflow,
    WorkflowAction,
    WorkflowCondition,
    WorkflowExecution,
    WorkflowActionExecution,
)


class WorkflowExecutor:
    """Handles workflow execution logic."""

    @staticmethod
    async def execute_workflow(
        workflow_id: UUID,
        entity_id: UUID,
        entity_type: str,
        entity_data: dict,
        db: AsyncSession,
        tenant_id: UUID,
    ) -> WorkflowExecution:
        """Execute a workflow for an entity."""
        # Get workflow
        workflow = await db.execute(
            select(Workflow).where(
                and_(Workflow.id == workflow_id, Workflow.tenant_id == tenant_id)
            )
        )
        wf = workflow.scalar_one_or_none()
        if not wf or not wf.is_active:
            return None

        # Create execution record
        execution = WorkflowExecution(
            workflow_id=workflow_id,
            entity_id=entity_id,
            entity_type=entity_type,
            status="IN_PROGRESS",
            execution_data=entity_data,
            tenant_id=tenant_id,
        )
        db.add(execution)
        await db.flush()

        try:
            # Evaluate conditions
            conditions = await db.execute(
                select(WorkflowCondition).where(
                    WorkflowCondition.workflow_id == workflow_id
                ).order_by(WorkflowCondition.order)
            )
            conds = conditions.scalars().all()

            # For now, simple AND logic - all conditions must pass
            conditions_passed = await WorkflowExecutor._evaluate_conditions(
                conds, entity_data
            )

            if not conditions_passed:
                execution.status = "SUCCESS"  # Conditions not met, no error
                await db.commit()
                return execution

            # Execute actions
            actions = await db.execute(
                select(WorkflowAction)
                .where(WorkflowAction.workflow_id == workflow_id)
                .order_by(WorkflowAction.order)
            )
            acts = actions.scalars().all()

            for action in acts:
                if not action.is_active:
                    continue

                action_exec = WorkflowActionExecution(
                    workflow_execution_id=execution.id,
                    workflow_action_id=action.id,
                    status="IN_PROGRESS",
                )
                db.add(action_exec)
                await db.flush()

                try:
                    result = await WorkflowExecutor._execute_action(
                        action.action_type, action.action_config, entity_data, db, tenant_id
                    )
                    action_exec.status = "SUCCESS"
                    action_exec.result_data = result
                except Exception as e:
                    action_exec.status = "FAILED"
                    action_exec.error_message = str(e)

                action_exec.completed_at = datetime.utcnow()

            execution.status = "SUCCESS"
        except Exception as e:
            execution.status = "FAILED"
            execution.error_message = str(e)

        execution.completed_at = datetime.utcnow()
        await db.commit()
        return execution

    @staticmethod
    async def _evaluate_conditions(conditions: list, entity_data: dict) -> bool:
        """Evaluate all conditions for workflow execution."""
        if not conditions:
            return True

        for condition in conditions:
            field_value = entity_data.get(condition.field_name)
            passed = WorkflowExecutor._evaluate_single_condition(
                field_value, condition.operator, condition.value
            )
            if not passed:
                return False

        return True

    @staticmethod
    def _evaluate_single_condition(field_value: any, operator: str, compare_value: str) -> bool:
        """Evaluate a single condition."""
        if operator == "equals":
            return str(field_value) == compare_value
        elif operator == "contains":
            return compare_value in str(field_value)
        elif operator == "greater_than":
            try:
                return float(field_value) > float(compare_value)
            except (ValueError, TypeError):
                return False
        elif operator == "less_than":
            try:
                return float(field_value) < float(compare_value)
            except (ValueError, TypeError):
                return False
        elif operator == "is_empty":
            return field_value is None or field_value == ""
        elif operator == "is_not_empty":
            return field_value is not None and field_value != ""
        else:
            return False

    @staticmethod
    async def _execute_action(
        action_type: str, action_config: dict, entity_data: dict, db: AsyncSession, tenant_id: UUID
    ) -> dict:
        """Execute a single workflow action."""
        if action_type == "send_notification":
            return await WorkflowExecutor._action_send_notification(action_config, entity_data)
        elif action_type == "assign_lead":
            return await WorkflowExecutor._action_assign_lead(action_config, entity_data, db)
        elif action_type == "create_task":
            return await WorkflowExecutor._action_create_task(action_config, entity_data)
        elif action_type == "update_field":
            return await WorkflowExecutor._action_update_field(action_config, entity_data)
        elif action_type == "send_email":
            return await WorkflowExecutor._action_send_email(action_config, entity_data)
        else:
            return {"status": "unknown_action", "action_type": action_type}

    @staticmethod
    async def _action_send_notification(config: dict, entity_data: dict) -> dict:
        """Send a notification action."""
        # Placeholder for notification sending
        return {
            "status": "notification_sent",
            "recipient": config.get("recipient_id"),
            "message": config.get("message", ""),
        }

    @staticmethod
    async def _action_assign_lead(config: dict, entity_data: dict, db: AsyncSession) -> dict:
        """Assign lead to a user action."""
        # Placeholder for lead assignment
        return {
            "status": "lead_assigned",
            "assigned_to": config.get("user_id"),
        }

    @staticmethod
    async def _action_create_task(config: dict, entity_data: dict) -> dict:
        """Create a task action."""
        # Placeholder for task creation
        return {
            "status": "task_created",
            "title": config.get("task_title", ""),
            "due_date": config.get("due_date", ""),
        }

    @staticmethod
    async def _action_update_field(config: dict, entity_data: dict) -> dict:
        """Update an entity field action."""
        # Placeholder for field update
        return {
            "status": "field_updated",
            "field": config.get("field_name"),
            "value": config.get("field_value"),
        }

    @staticmethod
    async def _action_send_email(config: dict, entity_data: dict) -> dict:
        """Send email action."""
        # Placeholder for email sending
        return {
            "status": "email_sent",
            "to": config.get("recipient_email"),
            "subject": config.get("subject", ""),
        }
