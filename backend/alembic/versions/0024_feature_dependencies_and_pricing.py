"""Add feature dependency, conflict, and billable pricing metadata."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0024_feature_dependencies_and_pricing"
down_revision = "0023_feature_registry_and_tenant_grants"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "feature_definitions",
        sa.Column("billable_amount", sa.Numeric(19, 4), nullable=True),
    )
    op.add_column(
        "feature_definitions",
        sa.Column(
            "dependency_keys", postgresql.JSONB(), nullable=False, server_default="[]"
        ),
    )
    op.add_column(
        "feature_definitions",
        sa.Column(
            "conflict_keys", postgresql.JSONB(), nullable=False, server_default="[]"
        ),
    )


def downgrade() -> None:
    op.drop_column("feature_definitions", "conflict_keys")
    op.drop_column("feature_definitions", "dependency_keys")
    op.drop_column("feature_definitions", "billable_amount")
