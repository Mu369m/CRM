"""FastAPI application entry point for the brokerage CRM."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .api import router as api_router
from .webhooks import router as webhook_router
from .auth_v1 import router as auth_v1_router
from .api_byodb import router as byodb_router
from .api.v1.owner.system_control import router as system_control_router
from .api.v1.broker.settings import router as broker_settings_router
from .api.v1.broker.custom_fields import router as custom_fields_router
from .api.v1.broker.pipelines import router as pipelines_router
from .api.v1.broker.leads import router as leads_router
from .api.v1.broker.departments import router as departments_router
from .api.v1.broker.teams import router as teams_router
from .api.v1.broker.roles import router as roles_router
from .api.v1.broker.clients import router as clients_router
from .api.v1.broker.ibs import router as ibs_router
from .api.v1.broker.deposits import router as deposits_router
from .api.v1.broker.withdrawals import router as withdrawals_router
from .api.v1.broker.documents import router as documents_router
from .api.v1.broker.audit import router as audit_router
from .api.v1.broker.ib_partners import router as ib_partners_router
from .api.v1.broker.transactions import router as transactions_router
from .api.v1.broker.kyc_documents import router as kyc_documents_router
from .api.v1.trader.accounts import router as trader_accounts_router
from .api.v1.trader.dashboard import router as trader_dashboard_router
from .api.v1.trader.profile import router as trader_profile_router
from .api.v1.trader.kyc import router as trader_kyc_router
from .api.v1.trader.ib import router as trader_ib_router
from .api.v1.trader.finance import router as trader_finance_router, payments_router
from .api.v1.broker.finance import router as finance_router
from .api.v1.broker.risk import router as risk_router

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Keep trading workers out of web processes; run them as a dedicated service."""
    yield


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "X-Tenant-Host", "X-Tenant-ID"],
)
app.include_router(api_router)
app.include_router(webhook_router)
app.include_router(auth_v1_router)
app.include_router(byodb_router)
app.include_router(system_control_router)
app.include_router(broker_settings_router)
app.include_router(custom_fields_router)
app.include_router(pipelines_router)
app.include_router(leads_router)
app.include_router(departments_router)
app.include_router(teams_router)
app.include_router(roles_router)
app.include_router(clients_router)
app.include_router(ibs_router)
app.include_router(deposits_router)
app.include_router(withdrawals_router)
app.include_router(documents_router)
app.include_router(audit_router)
app.include_router(ib_partners_router)
app.include_router(transactions_router)
app.include_router(kyc_documents_router)
app.include_router(trader_accounts_router)
app.include_router(trader_dashboard_router)
app.include_router(trader_profile_router)
app.include_router(trader_kyc_router)
app.include_router(trader_ib_router)
app.include_router(trader_finance_router)
app.include_router(payments_router)
app.include_router(finance_router)
app.include_router(risk_router)


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    """Return a lightweight liveness response without touching business data."""
    return {"status": "healthy", "service": settings.app_name}
