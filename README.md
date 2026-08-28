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
