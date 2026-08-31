"""Add deposits and withdrawals transaction tables.

Revision ID: 0015_deposits_withdrawals
Revises: 0014_ib_affiliate
Create Date: 2026-08-29 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0015_deposits_withdrawals'
down_revision = '0014_ib_affiliate'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create deposit_methods table
    op.create_table(
        'deposit_methods',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('provider', sa.String(), nullable=False),
        sa.Column('method_type', sa.String(), nullable=False),
        sa.Column('min_amount', sa.Numeric(), nullable=True),
        sa.Column('max_amount', sa.Numeric(), nullable=True),
        sa.Column('processing_fee_percent', sa.Numeric(), nullable=False, server_default='0'),
        sa.Column('processing_time_hours', sa.Integer(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('requires_verification', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    
    # Create deposits table
    op.create_table(
        'deposits',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('client_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('amount', sa.Numeric(), nullable=False),
        sa.Column('currency', sa.String(), nullable=False),
        sa.Column('method_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('method_name', sa.String(), nullable=False),
        sa.Column('payment_reference', sa.String(), nullable=True),
        sa.Column('status', sa.String(), nullable=False, server_default='PENDING'),
        sa.Column('processing_fee', sa.Numeric(), nullable=False, server_default='0'),
        sa.Column('net_amount', sa.Numeric(), nullable=False),
        sa.Column('approved_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('rejected_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('rejection_reason', sa.String(), nullable=True),
        sa.Column('approved_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['approved_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['method_id'], ['deposit_methods.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['rejected_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    
    # Create withdrawal_methods table
    op.create_table(
        'withdrawal_methods',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('provider', sa.String(), nullable=False),
        sa.Column('method_type', sa.String(), nullable=False),
        sa.Column('min_amount', sa.Numeric(), nullable=True),
        sa.Column('max_amount', sa.Numeric(), nullable=True),
        sa.Column('processing_fee_percent', sa.Numeric(), nullable=False, server_default='0'),
        sa.Column('processing_time_hours', sa.Integer(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('requires_verification', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    
    # Create withdrawals table
    op.create_table(
        'withdrawals',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('client_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('amount', sa.Numeric(), nullable=False),
        sa.Column('currency', sa.String(), nullable=False),
        sa.Column('method_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('method_name', sa.String(), nullable=False),
        sa.Column('payment_reference', sa.String(), nullable=True),
        sa.Column('status', sa.String(), nullable=False, server_default='PENDING'),
        sa.Column('processing_fee', sa.Numeric(), nullable=False, server_default='0'),
        sa.Column('net_amount', sa.Numeric(), nullable=False),
        sa.Column('approved_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('rejected_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('rejection_reason', sa.String(), nullable=True),
        sa.Column('approved_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['approved_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['method_id'], ['withdrawal_methods.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['rejected_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    
    # Create indexes
    op.create_index('idx_deposits_tenant_id', 'deposits', ['tenant_id'])
    op.create_index('idx_deposits_client_id', 'deposits', ['client_id'])
    op.create_index('idx_deposits_status', 'deposits', ['status'])
    op.create_index('idx_deposits_created', 'deposits', ['created_at'])
    op.create_index('idx_withdrawals_tenant_id', 'withdrawals', ['tenant_id'])
    op.create_index('idx_withdrawals_client_id', 'withdrawals', ['client_id'])
    op.create_index('idx_withdrawals_status', 'withdrawals', ['status'])
    op.create_index('idx_withdrawals_created', 'withdrawals', ['created_at'])


def downgrade() -> None:
    op.drop_index('idx_withdrawals_created', table_name='withdrawals')
    op.drop_index('idx_withdrawals_status', table_name='withdrawals')
    op.drop_index('idx_withdrawals_client_id', table_name='withdrawals')
    op.drop_index('idx_withdrawals_tenant_id', table_name='withdrawals')
    op.drop_index('idx_deposits_created', table_name='deposits')
    op.drop_index('idx_deposits_status', table_name='deposits')
    op.drop_index('idx_deposits_client_id', table_name='deposits')
    op.drop_index('idx_deposits_tenant_id', table_name='deposits')
    op.drop_table('withdrawals')
    op.drop_table('withdrawal_methods')
    op.drop_table('deposits')
    op.drop_table('deposit_methods')
