"""Finance approval queues, wallet settlement, and payment gateways."""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ....db import get_db
from ....models import LedgerEntry, LedgerEntryType, PaymentGateway, PaymentGatewayType, Role, Transaction, TransactionStatus, TransactionType, Wallet
from ....security import require_roles

router = APIRouter(tags=["Finance"])


class GatewayConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    wallet_address: str | None = Field(default=None, max_length=500)
    qr_code: str | None = Field(default=None, max_length=500)
    iban: str | None = Field(default=None, max_length=80)
    swift: str | None = Field(default=None, max_length=40)
    fee_percentage: Decimal = Field(default=Decimal("0"), ge=0, le=100, max_digits=8, decimal_places=4)


class GatewayPayload(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    type: PaymentGatewayType
    is_active: bool = True
    config_json: GatewayConfig = Field(default_factory=GatewayConfig)


class GatewayResponse(GatewayPayload):
    model_config = ConfigDict(from_attributes=True)
    id: UUID


class TransactionRequest(BaseModel):
    type: TransactionType
    amount: Decimal = Field(gt=0, max_digits=20, decimal_places=8)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    gateway_id: UUID | None = None
    payment_proof_url: str | None = Field(default=None, max_length=500)


class TransactionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    trader_id: UUID
    type: TransactionType
    amount: Decimal
    currency: str
    status: TransactionStatus
    gateway_id: UUID | None
    payment_proof_url: str | None
    rejection_note: str | None
    created_at: datetime


class TransactionPage(BaseModel):
    items: list[TransactionResponse]
    total: int
    offset: int
    limit: int


class RejectionPayload(BaseModel):
    note: str = Field(min_length=1, max_length=500)


class SettlementResponse(BaseModel):
    transaction: TransactionResponse
    wallet_balance: Decimal


broker_claims = Annotated[dict[str, str], Depends(require_roles(Role.SUPER_ADMIN, Role.BROKER_ADMIN, Role.FINANCE))]


@router.post("/api/v1/trader/finance/request", response_model=TransactionResponse, status_code=status.HTTP_202_ACCEPTED)
async def request_finance_transaction(payload: TransactionRequest, claims: Annotated[dict[str, str], Depends(require_roles(Role.TRADER))], db: AsyncSession = Depends(get_db)) -> Transaction:
    if payload.gateway_id:
        gateway = await db.scalar(select(PaymentGateway).where(PaymentGateway.id == payload.gateway_id, PaymentGateway.tenant_id == UUID(claims["tenant_id"]), PaymentGateway.is_active.is_(True)))
        if not gateway:
            raise HTTPException(status_code=404, detail="Active payment gateway not found")
    transaction = Transaction(tenant_id=UUID(claims["tenant_id"]), trader_id=UUID(claims["sub"]), **payload.model_dump())
    db.add(transaction)
    await db.commit()
    await db.refresh(transaction)
    return transaction


@router.get("/api/v1/broker/finance/transactions", response_model=TransactionPage)
async def list_transactions(
    claims: broker_claims,
    db: AsyncSession = Depends(get_db),
    transaction_status: TransactionStatus | None = Query(default=None, alias="status"),
    transaction_type: TransactionType | None = Query(default=None, alias="type"),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=25, ge=1, le=100),
) -> TransactionPage:
    tenant_id = UUID(claims["tenant_id"])
    filters = [Transaction.tenant_id == tenant_id]
    if transaction_status:
        filters.append(Transaction.status == transaction_status)
    if transaction_type:
        filters.append(Transaction.type == transaction_type)
    items = await db.scalars(select(Transaction).where(*filters).order_by(Transaction.created_at.desc()).offset(offset).limit(limit))
    total = await db.scalar(select(func.count(Transaction.id)).where(*filters))
    return TransactionPage(items=list(items), total=total or 0, offset=offset, limit=limit)


@router.post("/api/v1/broker/finance/transactions/{transaction_id}/approve", response_model=SettlementResponse)
async def approve_transaction(transaction_id: UUID, claims: broker_claims, db: AsyncSession = Depends(get_db)) -> SettlementResponse:
    transaction = await db.scalar(select(Transaction).where(Transaction.id == transaction_id, Transaction.tenant_id == UUID(claims["tenant_id"])).with_for_update())
    if not transaction or transaction.status != TransactionStatus.PENDING:
        raise HTTPException(status_code=404, detail="Pending transaction not found")
    wallet = await db.scalar(select(Wallet).where(Wallet.owner_id == transaction.trader_id, Wallet.tenant_id == transaction.tenant_id, Wallet.currency == transaction.currency).with_for_update())
    if not wallet:
        wallet = Wallet(tenant_id=transaction.tenant_id, owner_id=transaction.trader_id, currency=transaction.currency, balance=Decimal("0"))
        db.add(wallet)
        await db.flush()
    signed_amount = transaction.amount if transaction.type == TransactionType.DEPOSIT else -transaction.amount
    if signed_amount < 0 and wallet.balance + signed_amount < 0:
        raise HTTPException(status_code=409, detail="Insufficient wallet balance")
    wallet.balance += signed_amount
    transaction.status = TransactionStatus.APPROVED
    transaction.rejection_note = None
    ledger_type = LedgerEntryType.DEPOSIT if signed_amount > 0 else LedgerEntryType.WITHDRAWAL
    db.add(LedgerEntry(wallet_id=wallet.id, entry_type=ledger_type, amount=signed_amount, reference=f"transaction:{transaction.id}", note=f"Approved {transaction.type.value.lower()}"))
    await db.commit()
    await db.refresh(transaction)
    return SettlementResponse(transaction=transaction, wallet_balance=wallet.balance)


@router.post("/api/v1/broker/finance/transactions/{transaction_id}/reject", response_model=TransactionResponse)
async def reject_transaction(transaction_id: UUID, payload: RejectionPayload, claims: broker_claims, db: AsyncSession = Depends(get_db)) -> Transaction:
    transaction = await db.scalar(select(Transaction).where(Transaction.id == transaction_id, Transaction.tenant_id == UUID(claims["tenant_id"])).with_for_update())
    if not transaction or transaction.status != TransactionStatus.PENDING:
        raise HTTPException(status_code=404, detail="Pending transaction not found")
    transaction.status = TransactionStatus.REJECTED
    transaction.rejection_note = payload.note.strip()
    await db.commit()
    await db.refresh(transaction)
    return transaction


@router.get("/api/v1/broker/finance/gateways", response_model=list[GatewayResponse])
async def list_gateways(claims: broker_claims, db: AsyncSession = Depends(get_db)) -> list[PaymentGateway]:
    gateways = await db.scalars(select(PaymentGateway).where(PaymentGateway.tenant_id == UUID(claims["tenant_id"])).order_by(PaymentGateway.name))
    return list(gateways)


@router.post("/api/v1/broker/finance/gateways", response_model=GatewayResponse, status_code=status.HTTP_201_CREATED)
async def create_gateway(payload: GatewayPayload, claims: broker_claims, db: AsyncSession = Depends(get_db)) -> PaymentGateway:
    gateway = PaymentGateway(tenant_id=UUID(claims["tenant_id"]), name=payload.name.strip(), type=payload.type, is_active=payload.is_active, config_json=payload.config_json.model_dump(mode="json"))
    db.add(gateway)
    await db.commit()
    await db.refresh(gateway)
    return gateway