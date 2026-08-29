"""Add KYC and document management tables.

Revision ID: 0016_kyc_documents
Revises: 0015_deposits_withdrawals
Create Date: 2026-08-29 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0016_kyc_documents'
down_revision = '0015_deposits_withdrawals'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create document_types table
    op.create_table(
        'document_types',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column('required_for_kyc', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('max_file_size_mb', sa.Integer(), nullable=False, server_default='10'),
        sa.Column('allowed_formats', sa.String(), nullable=False, server_default='pdf,jpg,png'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'name'),
    )
    
    # Create kyc_documents table
    op.create_table(
        'kyc_documents',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('client_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('document_type_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('file_name', sa.String(), nullable=False),
        sa.Column('file_path', sa.String(), nullable=False),
        sa.Column('file_size_bytes', sa.Integer(), nullable=False),
        sa.Column('mime_type', sa.String(), nullable=False),
        sa.Column('uploaded_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('status', sa.String(), nullable=False, server_default='PENDING'),
        sa.Column('rejection_reason', sa.String(), nullable=True),
        sa.Column('approved_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('rejected_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('approved_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['approved_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['document_type_id'], ['document_types.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['rejected_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['uploaded_by'], ['users.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
    )
    
    # Create kyc_approvals table (KYC verification workflow)
    op.create_table(
        'kyc_approvals',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('client_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('kyc_level', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False, server_default='PENDING'),
        sa.Column('notes', sa.String(), nullable=True),
        sa.Column('verified_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('verified_at', sa.DateTime(), nullable=True),
        sa.Column('rejection_reason', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['verified_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('client_id', 'kyc_level'),
    )
    
    # Create indexes
    op.create_index('idx_document_types_tenant', 'document_types', ['tenant_id'])
    op.create_index('idx_kyc_documents_tenant_client', 'kyc_documents', ['tenant_id', 'client_id'])
    op.create_index('idx_kyc_documents_status', 'kyc_documents', ['status'])
    op.create_index('idx_kyc_approvals_tenant_client', 'kyc_approvals', ['tenant_id', 'client_id'])
    op.create_index('idx_kyc_approvals_status', 'kyc_approvals', ['status'])


def downgrade() -> None:
    op.drop_index('idx_kyc_approvals_status', table_name='kyc_approvals')
    op.drop_index('idx_kyc_approvals_tenant_client', table_name='kyc_approvals')
    op.drop_index('idx_kyc_documents_status', table_name='kyc_documents')
    op.drop_index('idx_kyc_documents_tenant_client', table_name='kyc_documents')
    op.drop_index('idx_document_types_tenant', table_name='document_types')
    op.drop_table('kyc_approvals')
    op.drop_table('kyc_documents')
    op.drop_table('document_types')
