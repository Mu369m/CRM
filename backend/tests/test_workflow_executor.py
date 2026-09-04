from uuid import uuid4

import pytest

from app.core.workflow_executor import WorkflowExecutor


@pytest.mark.asyncio
async def test_workflow_execute_action_passes_db_and_tenant_scope() -> None:
    class FakeDB:
        def __init__(self) -> None:
            self.added = []

        def add(self, instance) -> None:
            self.added.append(instance)

        async def flush(self) -> None:
            return None

    tenant_id = uuid4()
    entity_id = uuid4()
    db = FakeDB()

    result = await WorkflowExecutor._execute_action(
        "create_task",
        {"title": "Follow up", "assigned_to_id": str(uuid4())},
        {
            "tenant_id": str(tenant_id),
            "entity_id": str(entity_id),
            "entity_type": "LEAD",
        },
        db,
        tenant_id,
    )

    assert result["status"] == "created"
    assert len(db.added) == 1
    assert db.added[0].tenant_id == tenant_id
    assert db.added[0].entity_id == entity_id


@pytest.mark.asyncio
async def test_workflow_update_field_changes_entity_data() -> None:
    entity_data = {"status": "new"}

    result = await WorkflowExecutor._action_update_field(
        {"field_name": "status", "value": "qualified"},
        entity_data,
    )

    assert entity_data["status"] == "qualified"
    assert result["field_name"] == "status"
    assert result["new_value"] == "qualified"
    assert result["previous_value"] == "new"


@pytest.mark.asyncio
async def test_workflow_create_task_builds_task_record() -> None:
    class FakeDB:
        def __init__(self) -> None:
            self.added = []

        def add(self, instance) -> None:
            self.added.append(instance)

        async def flush(self) -> None:
            return None

    tenant_id = uuid4()
    entity_id = uuid4()
    assignee_id = uuid4()
    db = FakeDB()

    result = await WorkflowExecutor._action_create_task(
        {
            "title": "Follow up lead",
            "description": "Review the lead profile",
            "assigned_to_id": str(assignee_id),
            "priority": "HIGH",
            "due_date": "2026-09-10T00:00:00Z",
        },
        {
            "tenant_id": str(tenant_id),
            "entity_id": str(entity_id),
            "entity_type": "LEAD",
            "title": "New lead",
        },
        db,
    )

    assert result["status"] == "created"
    assert len(db.added) == 1
    assert db.added[0].title == "Follow up lead"
    assert db.added[0].tenant_id == tenant_id
    assert db.added[0].entity_id == entity_id
