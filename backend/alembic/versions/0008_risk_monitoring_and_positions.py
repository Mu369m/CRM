"""Add open positions, trade history, and tenant risk rules."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0008_risk_monitoring_and_positions"
down_revision = "0007_finance_and_payment_gateways"
branch_labels = None
depends_on = None


def upgrade() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    op.create_table("positions", sa.Column("id", uuid, primary_key=True), sa.Column("tenant_id", uuid, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False), sa.Column("trader_id", uuid, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False), sa.Column("account_id", uuid, sa.ForeignKey("trading_accounts.id", ondelete="CASCADE"), nullable=False), sa.Column("symbol", sa.String(32), nullable=False), sa.Column("volume", sa.Numeric(20, 8), nullable=False), sa.Column("side", sa.String(10), nullable=False), sa.Column("open_price", sa.Numeric(20, 8), nullable=False), sa.Column("current_price", sa.Numeric(20, 8), nullable=False), sa.Column("sl", sa.Numeric(20, 8)), sa.Column("tp", sa.Numeric(20, 8)), sa.Column("floating_pnl", sa.Numeric(20, 8), nullable=False, server_default="0"), sa.Column("swap", sa.Numeric(20, 8), nullable=False, server_default="0"), sa.Column("commission", sa.Numeric(20, 8), nullable=False, server_default="0"), sa.Column("opened_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column("is_open", sa.Boolean(), nullable=False, server_default=sa.true()), sa.Column("closed_at", sa.DateTime(timezone=True)))
    for index_name, column in (("ix_positions_tenant_id", "tenant_id"), ("ix_positions_trader_id", "trader_id"), ("ix_positions_account_id", "account_id"), ("ix_positions_symbol", "symbol"), ("ix_positions_is_open", "is_open")):
        op.create_index(index_name, "positions", [column])
    op.create_table("trade_history", sa.Column("id", uuid, primary_key=True), sa.Column("tenant_id", uuid, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False), sa.Column("trader_id", uuid, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False), sa.Column("account_id", uuid, sa.ForeignKey("trading_accounts.id", ondelete="CASCADE"), nullable=False), sa.Column("symbol", sa.String(32), nullable=False), sa.Column("volume", sa.Numeric(20, 8), nullable=False), sa.Column("side", sa.String(10), nullable=False), sa.Column("open_price", sa.Numeric(20, 8), nullable=False), sa.Column("close_price", sa.Numeric(20, 8), nullable=False), sa.Column("realized_pnl", sa.Numeric(20, 8), nullable=False), sa.Column("closed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column("close_reason", sa.String(80), nullable=False))
    for index_name, column in (("ix_trade_history_tenant_id", "tenant_id"), ("ix_trade_history_trader_id", "trader_id"), ("ix_trade_history_account_id", "account_id")):
        op.create_index(index_name, "trade_history", [column])
    op.create_table("risk_rules", sa.Column("id", uuid, primary_key=True), sa.Column("tenant_id", uuid, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False), sa.Column("max_leverage", sa.Integer(), nullable=False, server_default="500"), sa.Column("margin_call_level", sa.Numeric(8, 4), nullable=False, server_default="100"), sa.Column("stop_out_level", sa.Numeric(8, 4), nullable=False, server_default="50"), sa.Column("max_lot_size", sa.Numeric(20, 8), nullable=False, server_default="100"), sa.Column("prohibited_symbols_json", postgresql.JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")), sa.Column("max_drawdown_alert", sa.Numeric(8, 4), nullable=False, server_default="20"), sa.UniqueConstraint("tenant_id", name="uq_risk_rule_tenant"))
    op.create_index("ix_risk_rules_tenant_id", "risk_rules", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_risk_rules_tenant_id", table_name="risk_rules")
    op.drop_table("risk_rules")
    for index_name in ("ix_trade_history_account_id", "ix_trade_history_trader_id", "ix_trade_history_tenant_id"):
        op.drop_index(index_name, table_name="trade_history")
    op.drop_table("trade_history")
    for index_name in ("ix_positions_is_open", "ix_positions_symbol", "ix_positions_account_id", "ix_positions_trader_id", "ix_positions_tenant_id"):
        op.drop_index(index_name, table_name="positions")
    op.drop_table("positions")