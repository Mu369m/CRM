-- Brokerage CRM domain schema. Run through Alembic in deployments; this file documents the contract.
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TYPE user_role AS ENUM ('SUPER_ADMIN', 'COMPLIANCE', 'FINANCE', 'SALES', 'TRADER');
CREATE TYPE kyc_status AS ENUM ('PENDING', 'APPROVED', 'REJECTED');
CREATE TYPE request_status AS ENUM ('PENDING', 'APPROVED', 'REJECTED', 'PROCESSING', 'COMPLETED');
CREATE TYPE account_platform AS ENUM ('MT4', 'MT5', 'CTRADER');

CREATE TABLE tenants (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(), name VARCHAR(160) NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  email VARCHAR(320) NOT NULL UNIQUE, password_hash VARCHAR(255) NOT NULL,
  role user_role NOT NULL DEFAULT 'TRADER', kyc_status kyc_status NOT NULL DEFAULT 'PENDING',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE wallets (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  owner_id UUID NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE, currency CHAR(3) NOT NULL DEFAULT 'USD',
  balance NUMERIC(20,8) NOT NULL DEFAULT 0 CHECK (balance >= 0), created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE ledger_entries (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(), wallet_id UUID NOT NULL REFERENCES wallets(id) ON DELETE RESTRICT,
  entry_type VARCHAR(30) NOT NULL, amount NUMERIC(20,8) NOT NULL, reference VARCHAR(120) NOT NULL UNIQUE,
  note TEXT, created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE kyc_documents (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE, document_type VARCHAR(50) NOT NULL,
  storage_key TEXT NOT NULL, status kyc_status NOT NULL DEFAULT 'PENDING', review_note TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(), reviewed_at TIMESTAMPTZ
);
CREATE TABLE trading_accounts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE, platform account_platform NOT NULL,
  external_login VARCHAR(80) NOT NULL, server VARCHAR(160) NOT NULL, is_demo BOOLEAN NOT NULL DEFAULT false,
  leverage INTEGER NOT NULL DEFAULT 100 CHECK (leverage BETWEEN 1 AND 2000), is_locked BOOLEAN NOT NULL DEFAULT false,
  provisioning_status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(), UNIQUE(platform, external_login, server)
);
CREATE TABLE money_requests (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE, kind VARCHAR(20) NOT NULL,
  amount NUMERIC(20,8) NOT NULL CHECK (amount > 0), currency CHAR(3) NOT NULL,
  status request_status NOT NULL DEFAULT 'PENDING', provider_reference VARCHAR(160), idempotency_key VARCHAR(120) NOT NULL UNIQUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(), reviewed_at TIMESTAMPTZ
);
CREATE TABLE payment_gateways (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  name VARCHAR(120) NOT NULL, type VARCHAR(20) NOT NULL, is_active BOOLEAN NOT NULL DEFAULT true,
  config_json JSONB NOT NULL DEFAULT '{}', UNIQUE(tenant_id, name)
);
CREATE TABLE transactions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  trader_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE, type VARCHAR(30) NOT NULL,
  amount NUMERIC(20,8) NOT NULL CHECK (amount > 0), currency CHAR(3) NOT NULL,
  status VARCHAR(20) NOT NULL DEFAULT 'PENDING', gateway_id UUID REFERENCES payment_gateways(id) ON DELETE SET NULL,
  payment_proof_url TEXT, rejection_note TEXT, created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE positions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  trader_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE, account_id UUID NOT NULL REFERENCES trading_accounts(id) ON DELETE CASCADE,
  symbol VARCHAR(32) NOT NULL, volume NUMERIC(20,8) NOT NULL CHECK (volume > 0), side VARCHAR(10) NOT NULL,
  open_price NUMERIC(20,8) NOT NULL, current_price NUMERIC(20,8) NOT NULL, sl NUMERIC(20,8), tp NUMERIC(20,8),
  floating_pnl NUMERIC(20,8) NOT NULL DEFAULT 0, swap NUMERIC(20,8) NOT NULL DEFAULT 0, commission NUMERIC(20,8) NOT NULL DEFAULT 0,
  opened_at TIMESTAMPTZ NOT NULL DEFAULT now(), is_open BOOLEAN NOT NULL DEFAULT true, closed_at TIMESTAMPTZ
);
CREATE TABLE trade_history (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  trader_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE, account_id UUID NOT NULL REFERENCES trading_accounts(id) ON DELETE CASCADE,
  symbol VARCHAR(32) NOT NULL, volume NUMERIC(20,8) NOT NULL, side VARCHAR(10) NOT NULL,
  open_price NUMERIC(20,8) NOT NULL, close_price NUMERIC(20,8) NOT NULL, realized_pnl NUMERIC(20,8) NOT NULL,
  closed_at TIMESTAMPTZ NOT NULL DEFAULT now(), close_reason VARCHAR(80) NOT NULL
);
CREATE TABLE risk_rules (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  max_leverage INTEGER NOT NULL DEFAULT 500, margin_call_level NUMERIC(8,4) NOT NULL DEFAULT 100,
  stop_out_level NUMERIC(8,4) NOT NULL DEFAULT 50, max_lot_size NUMERIC(20,8) NOT NULL DEFAULT 100,
  prohibited_symbols_json JSONB NOT NULL DEFAULT '[]', max_drawdown_alert NUMERIC(8,4) NOT NULL DEFAULT 20,
  UNIQUE(tenant_id)
);
CREATE TABLE tenant_settings (
  tenant_id UUID PRIMARY KEY REFERENCES tenants(id) ON DELETE CASCADE,
  primary_color VARCHAR(20) NOT NULL DEFAULT '#45b69c', secondary_color VARCHAR(20) NOT NULL DEFAULT '#1d3430',
  logo_url TEXT, favicon_url TEXT, meta_title VARCHAR(160) NOT NULL DEFAULT 'Brokerage CRM', support_email VARCHAR(320),
  max_ib_levels INTEGER NOT NULL DEFAULT 5, tenant_schema VARCHAR(80) NOT NULL UNIQUE,
  kyc_schema JSONB NOT NULL DEFAULT '{}'
);
CREATE TABLE ib_partners (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE, parent_id UUID REFERENCES ib_partners(id), referral_code VARCHAR(50) NOT NULL UNIQUE,
  commission_rate NUMERIC(12,6) NOT NULL DEFAULT 0 CHECK (commission_rate >= 0), created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE webhook_events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,
  provider VARCHAR(80) NOT NULL, event_id VARCHAR(180) NOT NULL, payload JSONB NOT NULL,
  processed_at TIMESTAMPTZ, created_at TIMESTAMPTZ NOT NULL DEFAULT now(), UNIQUE(provider, event_id)
);
CREATE TABLE audit_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  actor_id UUID NOT NULL, action VARCHAR(120) NOT NULL, metadata_json JSONB NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_documents_review_queue ON kyc_documents(tenant_id, status, created_at);
CREATE INDEX idx_money_requests_queue ON money_requests(tenant_id, status, created_at);
CREATE INDEX idx_transactions_queue ON transactions(tenant_id, status, created_at);
CREATE INDEX idx_positions_queue ON positions(tenant_id, is_open, opened_at);
CREATE INDEX idx_trade_history_timeline ON trade_history(tenant_id, closed_at DESC);
CREATE INDEX idx_ib_parent ON ib_partners(tenant_id, parent_id);
CREATE INDEX idx_audit_timeline ON audit_logs(tenant_id, created_at DESC);
