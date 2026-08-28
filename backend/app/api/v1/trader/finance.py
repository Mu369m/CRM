"""Trader payment intents and signed payment confirmation."""

import json
from decimal import Decimal
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from ....config import get_settings
from ....core.db_router import get_tenant_db, get_tenant_engine
from ....db import SessionFactory
from ....events import verify_hmac
from ....models import LedgerEntry, MoneyRequest, PaymentGateway, PaymentGatewayType, RequestStatus, Role, Wallet
from ....models.master import BrokerTenant
from ....security import require_roles

router = APIRouter(prefix="/api/v1/trader/finance", tags=["Trader Payments"])
payments_router = APIRouter(prefix="/api/v1/payments", tags=["Payments"])
Claims = Annotated[dict[str, str], Depends(require_roles(Role.TRADER, Role.IB_PARTNER))]


@router.post("/deposit/crypto")
async def crypto_deposit(payload: dict[str, str], claims: Claims, db: AsyncSession = Depends(get_tenant_db), x_idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")):
    if not x_idempotency_key:
        raise HTTPException(status_code=400, detail="Idempotency-Key is required")
    existing = await db.scalar(select(MoneyRequest).where(MoneyRequest.idempotency_key == x_idempotency_key, MoneyRequest.tenant_id == UUID(claims["tenant_id"])))
    if existing:
        return {"id": existing.id, "status": existing.status, "address": existing.provider_reference, "network": "TRC20"}
    amount = Decimal(payload.get("amount", "0"))
    if amount <= 0: raise HTTPException(status_code=422, detail="Valid deposit amount is required")
    gateway = await db.scalar(select(PaymentGateway).where(PaymentGateway.tenant_id == UUID(claims["tenant_id"]), PaymentGateway.type == PaymentGatewayType.CRYPTO, PaymentGateway.is_active.is_(True)).order_by(PaymentGateway.name))
    if not gateway or not gateway.config_json.get("wallet_address"):
        raise HTTPException(status_code=503, detail="Crypto gateway is not configured")
    request = MoneyRequest(tenant_id=UUID(claims["tenant_id"]), user_id=UUID(claims["sub"]), kind="DEPOSIT", amount=amount, currency="USDT", status=RequestStatus.PENDING, provider_reference=gateway.config_json["wallet_address"], idempotency_key=x_idempotency_key)
    db.add(request)
    await db.commit()
    return {"id": request.id, "status": request.status, "address": request.provider_reference, "network": gateway.config_json.get("network", "TRC20"), "qr_code": f"https://quickchart.io/qr?text={request.provider_reference}"}


@router.post("/withdraw")
async def withdraw(payload: dict[str, str], claims: Claims, db: AsyncSession = Depends(get_tenant_db), x_idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")):
    if not x_idempotency_key:
        raise HTTPException(status_code=400, detail="Idempotency-Key is required")
    amount = Decimal(payload.get("amount", "0"))
    destination = payload.get("destination", "").strip()
    if amount <= 0 or not destination: raise HTTPException(status_code=422, detail="Valid amount and destination are required")
    existing = await db.scalar(select(MoneyRequest).where(MoneyRequest.idempotency_key == x_idempotency_key, MoneyRequest.tenant_id == UUID(claims["tenant_id"])))
    if existing: return {"id": existing.id, "status": existing.status}
    wallet = await db.scalar(select(Wallet).where(Wallet.owner_id == UUID(claims["sub"]), Wallet.tenant_id == UUID(claims["tenant_id"]), Wallet.currency == "USD").with_for_update())
    if not wallet or wallet.balance < amount: raise HTTPException(status_code=409, detail="Insufficient wallet balance")
    wallet.balance -= amount
    request = MoneyRequest(tenant_id=UUID(claims["tenant_id"]), user_id=UUID(claims["sub"]), kind="WITHDRAWAL", amount=amount, currency="USD", status=RequestStatus.PENDING, provider_reference=destination, idempotency_key=x_idempotency_key)
    db.add(request)
    await db.flush()
    db.add(LedgerEntry(wallet_id=wallet.id, entry_type="WITHDRAWAL", amount=-amount, reference=f"withdrawal:{request.id}", note="Withdrawal hold"))
    await db.commit()
    return {"id": request.id, "status": request.status, "amount": amount}


@router.post("/status/{request_id}")
async def payment_status(request_id: UUID, claims: Claims, db: AsyncSession = Depends(get_tenant_db)):
    request = await db.scalar(select(MoneyRequest).where(MoneyRequest.id == request_id, MoneyRequest.user_id == UUID(claims["sub"]), MoneyRequest.tenant_id == UUID(claims["tenant_id"])))
    if not request: raise HTTPException(status_code=404, detail="Payment request not found")
    return {"id": request.id, "kind": request.kind, "amount": request.amount, "currency": request.currency, "status": request.status, "created_at": request.created_at}


@payments_router.post("/webhook", include_in_schema=False)
async def payment_webhook(request: Request, x_signature: str = Header(default="")):
    body = await request.body()
    if not verify_hmac(body, x_signature, get_settings().webhook_signing_secret.get_secret_value()): raise HTTPException(status_code=401, detail="Invalid webhook signature")
    payload = json.loads(body)
    tenant_id = UUID(payload["tenant_id"]); request_id = UUID(payload["request_id"])
    async with SessionFactory() as master_db:
        broker = await master_db.get(BrokerTenant, tenant_id)
    if not broker: raise HTTPException(status_code=404, detail="Tenant not found")
    factory = SessionFactory
    if broker.encrypted_db_url:
        engine = await get_tenant_engine(broker); factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        payment = await db.scalar(select(MoneyRequest).where(MoneyRequest.id == request_id, MoneyRequest.tenant_id == tenant_id).with_for_update())
        if not payment: raise HTTPException(status_code=404, detail="Payment request not found")
        if payment.status == RequestStatus.COMPLETED: return {"accepted": True, "duplicate": True}
        payment.status = RequestStatus.COMPLETED if payload.get("status") == "COMPLETED" else RequestStatus.REJECTED
        payment.provider_reference = str(payload.get("provider_reference") or payment.provider_reference)
        if payment.status == RequestStatus.COMPLETED and payment.kind == "DEPOSIT":
            wallet = await db.scalar(select(Wallet).where(Wallet.owner_id == payment.user_id, Wallet.tenant_id == tenant_id, Wallet.currency == payment.currency).with_for_update())
            if not wallet:
                wallet = Wallet(tenant_id=tenant_id, owner_id=payment.user_id, currency=payment.currency, balance=Decimal("0")); db.add(wallet); await db.flush()
            wallet.balance += payment.amount
            db.add(LedgerEntry(wallet_id=wallet.id, entry_type="DEPOSIT", amount=payment.amount, reference=f"payment:{payment.id}", note="Confirmed payment webhook"))
        await db.commit()
    return {"accepted": True, "duplicate": False}
