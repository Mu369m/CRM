"""Workflow execution engine for processing workflow automations."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Activity,
    Lead,
    Task,
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
                select(WorkflowCondition)
                .where(WorkflowCondition.workflow_id == workflow_id)
                .order_by(WorkflowCondition.order)
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
                        action.action_type,
                        action.action_config,
                        entity_data,
                        db,
                        tenant_id,
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
    def _evaluate_single_condition(
        field_value: any, operator: str, compare_value: str
    ) -> bool:
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
        action_type: str,
        action_config: dict,
        entity_data: dict,
        db: AsyncSession,
        tenant_id: UUID,
    ) -> dict:
        """Execute a single workflow action."""
        if action_type == "send_notification":
            return await WorkflowExecutor._action_send_notification(
                action_config,
                {
                    **entity_data,
                    "tenant_id": tenant_id,
                    "entity_type": entity_data.get("entity_type", "GENERIC"),
                },
                db,
            )
        elif action_type == "assign_lead":
            return await WorkflowExecutor._action_assign_lead(
                action_config,
                {**entity_data, "tenant_id": tenant_id},
                db,
            )
        elif action_type == "create_task":
            return await WorkflowExecutor._action_create_task(
                action_config,
                {**entity_data, "tenant_id": tenant_id},
                db,
            )
        elif action_type == "update_field":
            return await WorkflowExecutor._action_update_field(
                action_config,
                entity_data,
            )
        elif action_type == "send_email":
            return await WorkflowExecutor._action_send_email(
                action_config,
                {
                    **entity_data,
                    "tenant_id": tenant_id,
                    "entity_type": entity_data.get("entity_type", "GENERIC"),
                },
                db,
            )
        else:
            raise ValueError(f"Unsupported workflow action: {action_type}")

    @staticmethod
    async def _action_send_notification(
        config: dict, entity_data: dict, db: AsyncSession | None = None
    ) -> dict:
        """Send a notification action."""
        message = (
            config.get("message")
            or entity_data.get("message")
            or "Workflow notification"
        )
        payload = {
            "channel": config.get("channel", "in_app"),
            "message": message,
            "recipient": config.get("recipient") or entity_data.get("email"),
        }

        if db and entity_data.get("tenant_id") and entity_data.get("entity_id"):
            tenant_id = entity_data["tenant_id"]
            if isinstance(tenant_id, str):
                tenant_id = UUID(tenant_id)
            entity_id = entity_data["entity_id"]
            if isinstance(entity_id, str):
                entity_id = UUID(entity_id)
            activity = Activity(
                tenant_id=tenant_id,
                entity_type=entity_data.get("entity_type", "GENERIC"),
                entity_id=entity_id,
                activity_type="NOTIFICATION",
                description=message,
                user_id=UUID(str(entity_data.get("actor_id")))
                if entity_data.get("actor_id")
                else None,
                metadata_json={"notification": payload},
            )
            db.add(activity)
            await db.flush()

        return {"status": "sent", "notification": payload}

    @staticmethod
    async def _action_assign_lead(
        config: dict, entity_data: dict, db: AsyncSession
    ) -> dict:
        """Assign lead to a user action."""
        assignee_id = (
            config.get("assignee_id")
            or config.get("assigned_to_id")
            or entity_data.get("assigned_to_id")
        )
        if assignee_id is None:
            raise ValueError("assignee_id is required for lead assignment")

        entity_id = entity_data.get("entity_id") or config.get("entity_id")
        if entity_id is None:
            raise ValueError("entity_id is required for lead assignment")

        tenant_id = entity_data.get("tenant_id") or config.get("tenant_id")
        if tenant_id is None:
            raise ValueError("tenant_id is required for lead assignment")

        if isinstance(tenant_id, str):
            tenant_id = UUID(tenant_id)
        if isinstance(entity_id, str):
            entity_id = UUID(entity_id)
        if isinstance(assignee_id, str):
            assignee_id = UUID(assignee_id)

        lead = await db.scalar(
            select(Lead).where(Lead.id == entity_id, Lead.tenant_id == tenant_id)
        )
        if not lead:
            return {
                "status": "skipped",
                "reason": "lead_not_found",
                "entity_id": str(entity_id),
            }

        lead.assigned_to_id = assignee_id
        await db.flush()
        return {
            "status": "assigned",
            "lead_id": str(lead.id),
            "assigned_to_id": str(assignee_id),
        }

    @staticmethod
    async def _action_create_task(
        config: dict, entity_data: dict, db: AsyncSession | None = None
    ) -> dict:
        """Create a task action."""
        title = config.get("title") or entity_data.get("title") or "Workflow task"
        description = config.get("description") or entity_data.get("description")
        tenant_id = entity_data.get("tenant_id") or config.get("tenant_id")
        entity_id = entity_data.get("entity_id") or config.get("entity_id")
        entity_type = (
            entity_data.get("entity_type") or config.get("entity_type") or "GENERIC"
        )
        assigned_to_id = config.get("assigned_to_id") or entity_data.get(
            "assigned_to_id"
        )
        priority = config.get("priority") or entity_data.get("priority") or "NORMAL"

        if tenant_id is None:
            raise ValueError("tenant_id is required for task creation")
        if entity_id is None:
            raise ValueError("entity_id is required for task creation")
        if assigned_to_id is None:
            raise ValueError("assigned_to_id is required for task creation")

        if isinstance(tenant_id, str):
            tenant_id = UUID(tenant_id)
        if isinstance(entity_id, str):
            entity_id = UUID(entity_id)
        if isinstance(assigned_to_id, str):
            assigned_to_id = UUID(assigned_to_id)

        due_date_value = config.get("due_date") or entity_data.get("due_date")
        due_date = None
        if due_date_value:
            if isinstance(due_date_value, str):
                try:
                    due_date = datetime.fromisoformat(
                        due_date_value.replace("Z", "+00:00")
                    )
                except ValueError:
                    due_date = None
            elif isinstance(due_date_value, datetime):
                due_date = due_date_value

        result = {
            "status": "created",
            "title": title,
            "entity_type": entity_type,
            "entity_id": str(entity_id),
            "assigned_to_id": str(assigned_to_id),
            "priority": priority,
        }

        if db is not None:
            task = Task(
                tenant_id=tenant_id,
                entity_type=str(entity_type),
                entity_id=entity_id,
                title=title,
                description=description,
                assigned_to_id=assigned_to_id,
                priority=str(priority),
                due_date=due_date,
            )
            db.add(task)
            await db.flush()
            result["task_id"] = str(task.id)

        return result

    @staticmethod
    async def _action_update_field(config: dict, entity_data: dict) -> dict:
        """Update an entity field action."""
        field_name = config.get("field_name") or config.get("field")
        if not field_name:
            raise ValueError("field_name is required for field update")

        previous_value = entity_data.get(field_name)
        new_value = config.get("value")
        entity_data[field_name] = new_value

        return {
            "status": "updated",
            "field_name": field_name,
            "previous_value": previous_value,
            "new_value": new_value,
        }

    @staticmethod
    async def _action_send_email(
        config: dict, entity_data: dict, db: AsyncSession | None = None
    ) -> dict:
        """Send email action."""
        recipient = config.get("recipient") or entity_data.get("email")
        subject = config.get("subject") or "Workflow notification"
        message = (
            config.get("message") or entity_data.get("message") or "Workflow email"
        )
        payload = {"recipient": recipient, "subject": subject, "message": message}

        if db and entity_data.get("tenant_id") and entity_data.get("entity_id"):
            tenant_id = entity_data["tenant_id"]
            if isinstance(tenant_id, str):
                tenant_id = UUID(tenant_id)
            entity_id = entity_data["entity_id"]
            if isinstance(entity_id, str):
                entity_id = UUID(entity_id)
            activity = Activity(
                tenant_id=tenant_id,
                entity_type=entity_data.get("entity_type", "GENERIC"),
                entity_id=entity_id,
                activity_type="EMAIL_SENT",
                description=f"Email queued: {subject}",
                user_id=UUID(str(entity_data.get("actor_id")))
                if entity_data.get("actor_id")
                else None,
                metadata_json={"email": payload},
            )
            db.add(activity)
            await db.flush()

        return {"status": "queued", "email": payload}
