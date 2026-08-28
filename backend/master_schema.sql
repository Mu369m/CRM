-- SaaS owner database only. Never run this file against a broker's private database.
CREATE TABLE IF NOT EXISTS broker_tenants (
  id UUID PRIMARY KEY,
  company_name VARCHAR(160) NOT NULL,
  subdomain VARCHAR(80) NOT NULL UNIQUE,
  custom_domain VARCHAR(255) UNIQUE,
  encrypted_db_url TEXT,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  subscription_status VARCHAR(30) NOT NULL DEFAULT 'TRIAL',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_broker_tenants_domains ON broker_tenants(subdomain, custom_domain);
