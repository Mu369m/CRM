"""Add IB/Affiliate management tables.

Revision ID: 0014_ib_affiliate
Revises: 0013_client_management
Create Date: 2026-08-29 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0014_ib_affiliate'
down_revision = '0013_client_management'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create ib_partners table
    op.create_table(
        'ib_partners',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('first_name', sa.String(), nullable=False),
        sa.Column('last_name', sa.String(), nullable=False),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('phone', sa.String(), nullable=True),
        sa.Column('company_name', sa.String(), nullable=True),
        sa.Column('country', sa.String(), nullable=True),
        sa.Column('ib_level', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('parent_ib_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('commission_tier', sa.String(), nullable=True),
        sa.Column('status', sa.String(), nullable=False, server_default='ACTIVE'),
        sa.Column('total_clients', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_commissions', sa.Numeric(), nullable=False, server_default='0'),
        sa.Column('total_deposits_referred', sa.Numeric(), nullable=False, server_default='0'),
        sa.Column('bank_account', sa.String(), nullable=True),
        sa.Column('payment_method', sa.String(), nullable=True),
        sa.Column('kyc_status', sa.String(), nullable=True),
        sa.Column('is_archived', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['parent_ib_id'], ['ib_partners.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email', 'tenant_id'),
    )
    
    # Create ib_relationships table (tracks clients referred by IBs)
    op.create_table(
        'ib_relationships',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('ib_partner_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('client_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('referred_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('status', sa.String(), nullable=False, server_default='ACTIVE'),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['ib_partner_id'], ['ib_partners.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('ib_partner_id', 'client_id'),
    )
    
    # Create ib_commissions table
    op.create_table(
        'ib_commissions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('ib_partner_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('commission_type', sa.String(), nullable=False),
        sa.Column('base_rate', sa.Numeric(), nullable=False),
        sa.Column('tier_level', sa.Integer(), nullable=True),
        sa.Column('min_turnover', sa.Numeric(), nullable=True),
        sa.Column('max_turnover', sa.Numeric(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('effective_from', sa.DateTime(), nullable=False),
        sa.Column('effective_to', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['ib_partner_id'], ['ib_partners.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    
    # Create ib_payouts table
    op.create_table(
        'ib_payouts',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('ib_partner_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('payout_period', sa.String(), nullable=False),
        sa.Column('total_commissions', sa.Numeric(), nullable=False),
        sa.Column('total_clients_referred', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(), nullable=False, server_default='PENDING'),
        sa.Column('payment_status', sa.String(), nullable=False, server_default='PENDING'),
        sa.Column('payment_date', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['ib_partner_id'], ['ib_partners.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    
    # Create indexes
    op.create_index('idx_ib_partners_tenant_id', 'ib_partners', ['tenant_id'])
    op.create_index('idx_ib_partners_email', 'ib_partners', ['email'])
    op.create_index('idx_ib_partners_parent', 'ib_partners', ['parent_ib_id'])
    op.create_index('idx_ib_relationships_tenant_ib', 'ib_relationships', ['tenant_id', 'ib_partner_id'])
    op.create_index('idx_ib_relationships_client', 'ib_relationships', ['client_id'])
    op.create_index('idx_ib_commissions_tenant', 'ib_commissions', ['tenant_id'])
    op.create_index('idx_ib_payouts_tenant', 'ib_payouts', ['tenant_id'])


def downgrade() -> None:
    op.drop_index('idx_ib_payouts_tenant', table_name='ib_payouts')
    op.drop_index('idx_ib_commissions_tenant', table_name='ib_commissions')
    op.drop_index('idx_ib_relationships_client', table_name='ib_relationships')
    op.drop_index('idx_ib_relationships_tenant_ib', table_name='ib_relationships')
    op.drop_index('idx_ib_partners_parent', table_name='ib_partners')
    op.drop_index('idx_ib_partners_email', table_name='ib_partners')
    op.drop_index('idx_ib_partners_tenant_id', table_name='ib_partners')
    op.drop_table('ib_payouts')
    op.drop_table('ib_commissions')
    op.drop_table('ib_relationships')
    op.drop_table('ib_partners')
