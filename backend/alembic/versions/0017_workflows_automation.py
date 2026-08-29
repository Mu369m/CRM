"""Add workflow and automation system tables.

Revision ID: 0017_workflows_automation
Revises: 0016_kyc_documents
Create Date: 2026-08-29 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0017_workflows_automation'
down_revision = '0016_kyc_documents'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create workflows table
    op.create_table(
        'workflows',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column('entity_type', sa.String(), nullable=False),  # 'lead', 'client', 'deposit', etc.
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('trigger_type', sa.String(), nullable=False),  # 'entity_created', 'status_changed', 'time_based'
        sa.Column('trigger_config', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'name'),
        sa.Index('ix_workflows_tenant_id', 'tenant_id'),
        sa.Index('ix_workflows_entity_type', 'entity_type'),
        sa.Index('ix_workflows_is_active', 'is_active'),
    )

    # Create workflow_actions table
    op.create_table(
        'workflow_actions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('workflow_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('action_type', sa.String(), nullable=False),  # 'send_notification', 'assign_lead', 'create_task', 'update_field', 'send_email'
        sa.Column('action_config', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.ForeignKeyConstraint(['workflow_id'], ['workflows.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.Index('ix_workflow_actions_workflow_id', 'workflow_id'),
        sa.Index('ix_workflow_actions_order', 'order'),
    )

    # Create workflow_conditions table
    op.create_table(
        'workflow_conditions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('workflow_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('field_name', sa.String(), nullable=False),
        sa.Column('operator', sa.String(), nullable=False),  # 'equals', 'contains', 'greater_than', 'less_than', 'is_empty', 'is_not_empty'
        sa.Column('value', sa.String(), nullable=True),
        sa.Column('logic_operator', sa.String(), nullable=False, server_default='AND'),  # 'AND', 'OR'
        sa.Column('order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['workflow_id'], ['workflows.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.Index('ix_workflow_conditions_workflow_id', 'workflow_id'),
    )

    # Create workflow_executions table
    op.create_table(
        'workflow_executions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('workflow_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('entity_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('entity_type', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False, server_default='PENDING'),  # 'PENDING', 'IN_PROGRESS', 'SUCCESS', 'FAILED'
        sa.Column('error_message', sa.String(), nullable=True),
        sa.Column('execution_data', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('started_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(['workflow_id'], ['workflows.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.Index('ix_workflow_executions_workflow_id', 'workflow_id'),
        sa.Index('ix_workflow_executions_entity_id', 'entity_id'),
        sa.Index('ix_workflow_executions_status', 'status'),
        sa.Index('ix_workflow_executions_tenant_id', 'tenant_id'),
    )

    # Create workflow_action_executions table
    op.create_table(
        'workflow_action_executions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('workflow_execution_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('workflow_action_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('status', sa.String(), nullable=False, server_default='PENDING'),  # 'PENDING', 'SUCCESS', 'FAILED'
        sa.Column('error_message', sa.String(), nullable=True),
        sa.Column('result_data', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('started_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['workflow_execution_id'], ['workflow_executions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['workflow_action_id'], ['workflow_actions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.Index('ix_workflow_action_executions_workflow_execution_id', 'workflow_execution_id'),
        sa.Index('ix_workflow_action_executions_status', 'status'),
    )


def downgrade() -> None:
    op.drop_table('workflow_action_executions')
    op.drop_table('workflow_executions')
    op.drop_table('workflow_conditions')
    op.drop_table('workflow_actions')
    op.drop_table('workflows')
