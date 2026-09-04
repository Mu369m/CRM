"""Add tenant-scoped draft and published theme versions."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0018_tenant_theme_versions"
down_revision = "0017_workflows_automation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tenant_theme_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "status", sa.String(length=20), nullable=False, server_default="DRAFT"
        ),
        sa.Column("config", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_tenant_theme_versions_tenant_id", "tenant_theme_versions", ["tenant_id"]
    )


def downgrade() -> None:
    op.drop_index(
        "ix_tenant_theme_versions_tenant_id", table_name="tenant_theme_versions"
    )
    op.drop_table("tenant_theme_versions")
