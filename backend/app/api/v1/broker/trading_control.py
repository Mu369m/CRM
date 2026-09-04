"""Tenant-scoped trading account controls and server-side bulk selection."""

from decimal import Decimal
import json
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, insert, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ....core.db_router import get_tenant_db
from ....models import AccountPlatform, AuditLog, Role, TradingAccount, User
from ....security import require_roles

router = APIRouter(prefix="/api/v1/broker/trading", tags=["Trading Control"])
BrokerClaims = Annotated[
    dict[str, str], Depends(require_roles(Role.SUPER_ADMIN, Role.BROKER_ADMIN))
]
SelectionType = Literal["ALL", "FILTERED", "SPECIFIC"]
BulkAction = Literal[
    "TRADING_ENABLE",
    "TRADING_DISABLE",
    "BUY_ENABLE",
    "BUY_DISABLE",
    "SELL_ENABLE",
    "SELL_DISABLE",
    "EA_ENABLE",
    "EA_DISABLE",
    "SET_MAX_LOT",
    "SET_MAX_OPEN_POSITIONS",
    "KILL_SWITCH",
]


class TradingAccountResponse(BaseModel):
    id: UUID
    user_id: UUID
    platform: AccountPlatform
    external_login: str
    server: str
    trading_enabled: bool
    buy_enabled: bool
    sell_enabled: bool
    ea_enabled: bool
    max_lot_size: Decimal
    max_open_positions: int


class TradingAccountPage(BaseModel):
    items: list[TradingAccountResponse]
    total: int
    selection_type: SelectionType
    offset: int
    limit: int


class BulkTradingRequest(BaseModel):
    selection_type: SelectionType
    account_ids: list[UUID] = Field(default_factory=list, max_length=10000)
    search: str | None = Field(default=None, max_length=160)
    platform: AccountPlatform | None = None
    action: BulkAction
    max_lot_size: Decimal | None = Field(
        default=None, gt=0, max_digits=20, decimal_places=8
    )
    max_open_positions: int | None = Field(default=None, ge=1, le=10000)
    confirm: bool = False
    reason: str | None = Field(default=None, max_length=500)


def _filters(tenant_id: UUID, search: str | None, platform: AccountPlatform | None):
    conditions = [TradingAccount.tenant_id == tenant_id]
    if search:
        term = f"%{search.strip()}%"
        conditions.append(
            or_(
                TradingAccount.external_login.ilike(term),
                TradingAccount.server.ilike(term),
            )
        )
    if platform:
        conditions.append(TradingAccount.platform == platform)
    return conditions


def _selection_query(payload: BulkTradingRequest, tenant_id: UUID):
    conditions = _filters(tenant_id, payload.search, payload.platform)
    if payload.selection_type == "SPECIFIC":
        if not payload.account_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Specific selection requires account_ids",
            )
        conditions.append(TradingAccount.id.in_(payload.account_ids))
    elif payload.account_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="account_ids are only valid for SPECIFIC selection",
        )
    return select(TradingAccount).where(*conditions)


@router.get("/accounts", response_model=TradingAccountPage)
async def list_trading_accounts(
    claims: BrokerClaims,
    db: AsyncSession = Depends(get_tenant_db),
    search: str | None = Query(default=None, max_length=160),
    platform: AccountPlatform | None = None,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> TradingAccountPage:
    tenant_id = UUID(claims["tenant_id"])
    conditions = _filters(tenant_id, search, platform)
    items = list(
        await db.scalars(
            select(TradingAccount)
            .where(*conditions)
            .order_by(TradingAccount.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
    )
    total = await db.scalar(select(func.count(TradingAccount.id)).where(*conditions))
    selection_type: SelectionType = "FILTERED" if search or platform else "ALL"
    return TradingAccountPage(
        items=items,
        total=total or 0,
        selection_type=selection_type,
        offset=offset,
        limit=limit,
    )


@router.post("/accounts/bulk", response_model=dict)
async def bulk_trading_action(
    payload: BulkTradingRequest,
    claims: BrokerClaims,
    db: AsyncSession = Depends(get_tenant_db),
) -> dict:
    tenant_id, actor_id = UUID(claims["tenant_id"]), UUID(claims["sub"])
    accounts = list(
        await db.scalars(_selection_query(payload, tenant_id).with_for_update())
    )
    affected_count = len(accounts)
    if affected_count == 0:
        return {
            "status": "NO_MATCHES",
            "affected_count": 0,
            "successful": 0,
            "failed": 0,
            "failed_records": [],
        }
    dangerous = payload.action.endswith("DISABLE") or payload.action == "KILL_SWITCH"
    if dangerous and not payload.confirm:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "CONFIRMATION_REQUIRED",
                "affected_count": affected_count,
                "action": payload.action,
            },
        )
    if payload.action == "SET_MAX_LOT" and payload.max_lot_size is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="max_lot_size is required"
        )
    if (
        payload.action == "SET_MAX_OPEN_POSITIONS"
        and payload.max_open_positions is None
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="max_open_positions is required",
        )

    changes: list[dict] = []
    for account in accounts:
        previous: dict[str, object] = {}
        new_values: dict[str, object] = {}
        if payload.action in {"TRADING_ENABLE", "TRADING_DISABLE", "KILL_SWITCH"}:
            previous["trading_enabled"] = account.trading_enabled
            account.trading_enabled = payload.action == "TRADING_ENABLE"
            new_values["trading_enabled"] = account.trading_enabled
        if payload.action in {"BUY_ENABLE", "BUY_DISABLE"}:
            previous["buy_enabled"] = account.buy_enabled
            account.buy_enabled = payload.action == "BUY_ENABLE"
            new_values["buy_enabled"] = account.buy_enabled
        if payload.action in {"SELL_ENABLE", "SELL_DISABLE"}:
            previous["sell_enabled"] = account.sell_enabled
            account.sell_enabled = payload.action == "SELL_ENABLE"
            new_values["sell_enabled"] = account.sell_enabled
        if payload.action in {"EA_ENABLE", "EA_DISABLE"}:
            previous["ea_enabled"] = account.ea_enabled
            account.ea_enabled = payload.action == "EA_ENABLE"
            new_values["ea_enabled"] = account.ea_enabled
        if payload.action == "SET_MAX_LOT":
            previous["max_lot_size"] = str(account.max_lot_size)
            account.max_lot_size = payload.max_lot_size
            new_values["max_lot_size"] = str(payload.max_lot_size)
        if payload.action == "SET_MAX_OPEN_POSITIONS":
            previous["max_open_positions"] = account.max_open_positions
            account.max_open_positions = payload.max_open_positions
            new_values["max_open_positions"] = payload.max_open_positions
        if payload.action == "KILL_SWITCH":
            previous["is_locked"] = account.is_locked
            account.is_locked = True
            new_values["is_locked"] = True
        changes.append(
            {"entity_id": str(account.id), "previous": previous, "new": new_values}
        )

    audit_rows = [
        {
            "tenant_id": tenant_id,
            "actor_id": actor_id,
            "action": f"TRADING:{payload.action}",
            "metadata_json": json.dumps(
                {
                    "entity_type": "TRADING_ACCOUNT",
                    "entity_id": change["entity_id"],
                    "selection_type": payload.selection_type,
                    "affected_count": affected_count,
                    "previous_value": change["previous"],
                    "new_value": change["new"],
                    "reason": payload.reason,
                }
            ),
        }
        for change in changes
    ]
    await db.execute(insert(AuditLog), audit_rows)
    await db.commit()
    return {
        "status": "COMPLETED",
        "affected_count": affected_count,
        "successful": affected_count,
        "failed": 0,
        "failed_records": [],
        "selection_type": payload.selection_type,
    }
