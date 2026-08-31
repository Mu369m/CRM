"""Add client management tables.

Revision ID: 0013_client_management
Revises: 0012_custom_fields_pipelines_rbac_leads
Create Date: 2026-08-29 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0013_client_management'
down_revision = '0012_custom_fields_pipelines_rbac_leads'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create clients table
    op.create_table(
        'clients',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('first_name', sa.String(), nullable=False),
        sa.Column('last_name', sa.String(), nullable=False),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('phone', sa.String(), nullable=True),
        sa.Column('country', sa.String(), nullable=True),
        sa.Column('trading_platform', sa.String(), nullable=True),
        sa.Column('account_type', sa.String(), nullable=True),
        sa.Column('assigned_user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('source', sa.String(), nullable=True),
        sa.Column('campaign_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('ib_partner_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('status', sa.String(), nullable=False, server_default='NEW'),
        sa.Column('total_deposits', sa.Numeric(), nullable=True),
        sa.Column('total_withdrawals', sa.Numeric(), nullable=True),
        sa.Column('net_deposits', sa.Numeric(), nullable=True),
        sa.Column('last_deposit_date', sa.DateTime(), nullable=True),
        sa.Column('last_withdrawal_date', sa.DateTime(), nullable=True),
        sa.Column('is_archived', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['assigned_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['campaign_id'], ['campaigns.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email', 'tenant_id'),
    )
    
    # Create client_accounts table
    op.create_table(
        'client_accounts',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('client_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('account_number', sa.String(), nullable=False),
        sa.Column('platform', sa.String(), nullable=False),
        sa.Column('server', sa.String(), nullable=True),
        sa.Column('trading_status', sa.String(), nullable=True),
        sa.Column('account_balance', sa.Numeric(), nullable=True),
        sa.Column('equity', sa.Numeric(), nullable=True),
        sa.Column('margin', sa.Numeric(), nullable=True),
        sa.Column('free_margin', sa.Numeric(), nullable=True),
        sa.Column('leverage', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('account_number', 'tenant_id'),
    )
    
    # Create client_financials table
    op.create_table(
        'client_financials',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('client_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('total_deposits', sa.Numeric(), nullable=False, server_default='0'),
        sa.Column('total_withdrawals', sa.Numeric(), nullable=False, server_default='0'),
        sa.Column('net_deposits', sa.Numeric(), nullable=False, server_default='0'),
        sa.Column('total_trading_volume', sa.Numeric(), nullable=False, server_default='0'),
        sa.Column('total_commissions_paid', sa.Numeric(), nullable=False, server_default='0'),
        sa.Column('total_profit_loss', sa.Numeric(), nullable=False, server_default='0'),
        sa.Column('last_updated', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('client_id', 'tenant_id'),
    )
    
    # Create indexes
    op.create_index('idx_clients_tenant_id', 'clients', ['tenant_id'])
    op.create_index('idx_clients_email', 'clients', ['email'])
    op.create_index('idx_clients_status', 'clients', ['status'])
    op.create_index('idx_clients_assigned_user', 'clients', ['assigned_user_id'])
    op.create_index('idx_client_accounts_tenant_client', 'client_accounts', ['tenant_id', 'client_id'])
    op.create_index('idx_client_financials_tenant', 'client_financials', ['tenant_id'])


def downgrade() -> None:
    op.drop_index('idx_client_financials_tenant', table_name='client_financials')
    op.drop_index('idx_client_accounts_tenant_client', table_name='client_accounts')
    op.drop_index('idx_clients_assigned_user', table_name='clients')
    op.drop_index('idx_clients_status', table_name='clients')
    op.drop_index('idx_clients_email', table_name='clients')
    op.drop_index('idx_clients_tenant_id', table_name='clients')
    op.drop_table('client_financials')
    op.drop_table('client_accounts')
    op.drop_table('clients')
