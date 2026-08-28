# Brokerage CRM

Institution-grade, multi-tenant brokerage CRM for trader onboarding, treasury, compliance, IB commissions, and MT4/MT5/cTrader integrations.

## Structure

- `frontend/`: Next.js App Router, TypeScript, Tailwind CSS
- `backend/`: FastAPI, async SQLAlchemy, PostgreSQL, Redis
- `docs/`: architecture and operational documentation

## Local development

1. Copy `backend/.env.example` to `backend/.env` and provide strong secrets.
2. Install frontend dependencies: `cd frontend && npm install`.
3. Install backend dependencies in a virtual environment: `cd backend && python -m pip install -r requirements.txt`.
4. Run the API: `uvicorn app.main:app --reload --port 8000`.
5. Run the web app: `npm run dev` from `frontend/`.

The existing `mt5` repository is separate and is not part of this project.

## BYODB deployment model

The SaaS master database stores broker registry metadata and an AES-256-GCM encrypted private database URL. Broker client records are migrated to and stored in the broker's own PostgreSQL database. Configure it through `PUT /api/v1/admin/settings/database` with a broker-admin JWT and `X-Tenant-ID`/tenant claims; the API verifies `SELECT 1`, runs the checked-in Alembic chain remotely, then replaces the cached tenant pool.

Run `backend/master_schema.sql` only against the SaaS master database. Never run it against a broker database. The remote tenant migration chain is managed by `backend/alembic` and never stores the master broker registry there.
