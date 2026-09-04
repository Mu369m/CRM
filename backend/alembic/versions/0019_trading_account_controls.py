"""Add tenant-scoped trading controls to accounts."""

from alembic import op
import sqlalchemy as sa

revision = "0019_trading_account_controls"
down_revision = "0018_tenant_theme_versions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "trading_accounts",
        sa.Column(
            "trading_enabled", sa.Boolean(), nullable=False, server_default="true"
        ),
    )
    op.add_column(
        "trading_accounts",
        sa.Column("buy_enabled", sa.Boolean(), nullable=False, server_default="true"),
    )
    op.add_column(
        "trading_accounts",
        sa.Column("sell_enabled", sa.Boolean(), nullable=False, server_default="true"),
    )
    op.add_column(
        "trading_accounts",
        sa.Column("ea_enabled", sa.Boolean(), nullable=False, server_default="true"),
    )
    op.add_column(
        "trading_accounts",
        sa.Column(
            "max_lot_size", sa.Numeric(20, 8), nullable=False, server_default="100"
        ),
    )
    op.add_column(
        "trading_accounts",
        sa.Column(
            "max_open_positions", sa.Integer(), nullable=False, server_default="100"
        ),
    )
    op.add_column(
        "trading_accounts",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    for column in (
        "updated_at",
        "max_open_positions",
        "max_lot_size",
        "ea_enabled",
        "sell_enabled",
        "buy_enabled",
        "trading_enabled",
    ):
        op.drop_column("trading_accounts", column)
