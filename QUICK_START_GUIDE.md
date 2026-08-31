# QUICK START GUIDE: Integrating Production Modules

## For Developers: Getting Started with New Production Modules

This guide shows how to integrate the 7 new production-ready modules into existing API endpoints.

---

## 🔧 SETUP

### 1. Database Migration
```bash
cd backend

# Generate migration for idempotency_key
alembic revision --autogenerate -m "Add transaction idempotency_key"

# Review the migration file
cat alembic/versions/xxxx_add_transaction_idempotency.py

# Apply the migration
alembic upgrade head

# Verify
alembic current
```

### 2. Import the Modules
```python
# In your endpoint files, add these imports at the top

from app.core.financial_safety import (
    process_withdrawal_atomically,
    process_deposit_atomically,
    get_wallet_balance_from_ledger,
    create_financial_audit_log,
)

from app.core.tenant_isolation import (
    assert_tenant_isolation,
    build_tenant_filter,
    validate_entity_ownership,
)

from app.core.external_api_resilience import (
    call_external_api_with_retry,
    RetryStrategy,
    ExternalErrorClassification,
)

from app.core.withdrawal_approval import (
    initiate_withdrawal,
    submit_for_review,
    approve_withdrawal,
    complete_withdrawal,
)

from app.core.client_lifecycle import (
    transition_client_status,
    ClientStatus,
)
```

---

## 📝 PATTERN 1: Protected Endpoint with Tenant Isolation

### Before (Current):
```python
@router.get("/clients")
async def list_clients(db: AsyncSession = Depends(get_db)):
    # No tenant validation!
    # Could see other broker's clients!
    clients = await db.execute(select(Client))
    return clients.scalars().all()
```

### After (Production-Ready):
```python
@router.get("/clients")
async def list_clients(
    claims: dict = Depends(assert_tenant_isolation),  # ← Validates tenant
    db: AsyncSession = Depends(get_tenant_db),
):
    tenant_id = UUID(claims["tenant_id"])
    
    # Query automatically filtered to this tenant
    clients = await db.execute(
        select(Client).where(
            build_tenant_filter(tenant_id, Client)  # ← Adds tenant_id WHERE clause
        )
    )
    return clients.scalars().all()
```

**Key Changes**:
1. Add `Depends(assert_tenant_isolation)` to route
2. Extract tenant_id from claims
3. Add `build_tenant_filter()` to every query WHERE clause
4. Use `get_tenant_db` instead of `get_db`

---

## 💰 PATTERN 2: Financial Operation with Atomic Safety

### Before (Current):
```python
@router.post("/withdrawals")
async def create_withdrawal(
    request: WithdrawalRequest,
    db: AsyncSession = Depends(get_db),
):
    # Just create record without safety checks!
    # Could withdraw twice!
    # Could overdraft!
    
    withdrawal = Withdrawal(
        client_id=request.client_id,
        amount=request.amount,
        status="PENDING",
    )
    db.add(withdrawal)
    await db.commit()
    return withdrawal
```

### After (Production-Ready):
```python
@router.post("/withdrawals")
async def create_withdrawal(
    request: WithdrawalRequest,
    claims: dict = Depends(assert_tenant_isolation),
    db: AsyncSession = Depends(get_tenant_db),
):
    tenant_id = UUID(claims["tenant_id"])
    user_id = UUID(claims["sub"])
    
    try:
        # Use atomic operation with all safety checks
        withdrawal_id, reserved_amount = await initiate_withdrawal(
            db=db,
            tenant_id=tenant_id,
            client_id=request.client_id,
            user_id=user_id,
            amount=request.amount,
            currency=request.currency,
            method_id=request.method_id,
            idempotency_key=request.idempotency_key,  # ← Prevents duplicates!
        )
        
        return {
            "id": withdrawal_id,
            "reserved_amount": reserved_amount,
            "status": "PENDING",
        }
        
    except Exception as e:
        # Error already classified and audited
        raise HTTPException(status_code=400, detail=str(e))
```

**Key Changes**:
1. Add idempotency_key to request
2. Call `initiate_withdrawal()` instead of manual creation
3. Amount is reserved immediately (wallet balance reduced)
4. Error handling is built-in

---

## 🔄 PATTERN 3: Webhook Handler with Deduplication

### Before (Current):
```python
@router.post("/webhooks/deposit")
async def handle_deposit_webhook(
    request: DepositWebhookRequest,
    db: AsyncSession = Depends(get_db),
):
    # Process webhook blindly
    # Could process twice if duplicate webhook!
    
    deposit = Deposit(
        client_id=request.client_id,
        amount=request.amount,
        status="COMPLETED",
    )
    db.add(deposit)
    await db.commit()
    return {"status": "ok"}
```

### After (Production-Ready):
```python
@router.post("/webhooks/deposit")
async def handle_deposit_webhook(
    request: DepositWebhookRequest,
    db: AsyncSession = Depends(get_db),
):
    tenant_id = request.tenant_id  # From webhook path or body
    
    try:
        # Use atomic operation with duplicate detection
        result = await process_deposit_atomically(
            db=db,
            tenant_id=tenant_id,
            wallet_id=request.wallet_id,
            user_id=request.client_id,
            amount=request.amount,
            currency=request.currency,
            provider=request.provider,
            provider_transaction_id=request.provider_id,  # ← For deduplication!
            idempotency_key=request.provider_id,  # ← Use provider ID
            metadata={"webhook_timestamp": request.timestamp},
        )
        
        if result.is_duplicate:
            # Webhook already processed - return success
            return {"status": "already_processed"}
        
        if result.success:
            return {"status": "processed"}
        else:
            # Non-retryable error - must handle manually
            return {"status": "failed", "reason": result.reason}
            
    except Exception as e:
        # Log but return 200 OK (webhook ack)
        # Don't let provider keep retrying
        logger.error(f"Webhook processing failed: {e}")
        return {"status": "error"}
```

**Key Changes**:
1. Call `process_deposit_atomically()` for atomic safety
2. Use provider event ID for deduplication
3. Check `is_duplicate` flag
4. Return 200 OK even on errors (ack webhook)
5. Manually investigate failed deposits later

---

## ⚙️ PATTERN 4: External API Call with Retry Logic

### Before (Current):
```python
async def process_withdrawal_to_provider(withdrawal_id):
    # No retry logic - fails on timeout!
    
    response = httpx.post(
        "https://payment-provider.com/withdraw",
        json={"amount": 1000, "reference": withdrawal_id},
        timeout=30,
    )
    
    if response.status_code != 200:
        raise Exception("Withdrawal failed")
    
    return response.json()
```

### After (Production-Ready):
```python
async def process_withdrawal_to_provider(withdrawal_id, amount):
    # Automatic retry with exponential backoff
    
    result = await call_external_api_with_retry(
        call_id=uuid4(),
        provider="stripe",
        endpoint="https://api.stripe.com/v1/charges",
        method="POST",
        headers={"Authorization": f"Bearer {STRIPE_KEY}"},
        payload={
            "amount": int(amount * 100),  # cents
            "currency": "usd",
            "idempotency_key": str(withdrawal_id),
        },
        retry_strategy=RetryStrategy(
            max_attempts=3,
            exponential_base=2.0,  # 1s, 2s, 4s between attempts
        ),
        timeout_seconds=30,
    )
    
    if result.success:
        # Got response from provider
        return result.data
    
    elif result.is_retryable:
        # Retry failed after max attempts
        # Mark as PENDING, will retry later
        logger.warning(f"Retryable error: {result.error_classification}")
        raise Exception(f"Provider unavailable: {result.reason}")
    
    else:
        # Non-retryable error (auth, validation, etc.)
        # Fail immediately
        logger.error(f"Non-retryable error: {result.error_classification}")
        raise Exception(f"Invalid request: {result.reason}")
```

**Key Changes**:
1. Use `call_external_api_with_retry()` for all provider calls
2. Set idempotency_key for safe retries
3. Check `result.is_retryable` to decide next action
4. Max attempts configured (default 3)
5. Exponential backoff built-in

---

## 👤 PATTERN 5: Client Status Transition with Audit

### Before (Current):
```python
@router.post("/clients/{id}/approve-kyc")
async def approve_kyc(
    client_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    # Just update status without validation
    client = await db.get(Client, client_id)
    client.status = "VERIFIED"
    await db.commit()
    return {"status": "verified"}
```

### After (Production-Ready):
```python
@router.post("/clients/{id}/approve-kyc")
async def approve_kyc(
    client_id: UUID,
    claims: dict = Depends(assert_tenant_isolation),
    db: AsyncSession = Depends(get_tenant_db),
):
    tenant_id = UUID(claims["tenant_id"])
    actor_id = UUID(claims["sub"])
    
    try:
        # Validate transition, audit, and create activity
        client = await approve_kyc(
            db=db,
            tenant_id=tenant_id,
            client_id=client_id,
            actor_id=actor_id,  # Who approved it
        )
        
        return {
            "id": client.id,
            "status": client.status,
            "updated_at": client.updated_at,
        }
        
    except ClientLifecycleError as e:
        raise HTTPException(status_code=400, detail=str(e))
```

**Key Changes**:
1. Use `approve_kyc()` function (validates transition)
2. Pass actor_id (for audit trail)
3. Invalid transitions automatically rejected
4. Status change automatically audited
5. Activity record created automatically

---

## 🧪 PATTERN 6: Broker Health Check (Master Admin Only)

### Before (Current):
```python
# Not available
```

### After (Production-Ready):
```python
@router.get("/admin/brokers/{id}/health")
async def get_broker_health(
    tenant_id: UUID,
    claims: dict = Depends(assert_tenant_isolation),
    db: AsyncSession = Depends(get_tenant_db),
):
    # Only SUPER_ADMIN can access
    if claims.get("role") != "SUPER_ADMIN":
        raise HTTPException(status_code=403, detail="Forbidden")
    
    health = await get_broker_health(db, tenant_id)
    
    return {
        "status": health.status.value,
        "api_healthy": health.api_healthy,
        "db_healthy": health.db_healthy,
        "payment_gateway_healthy": health.payment_gateway_healthy,
        "trading_platform_healthy": health.trading_platform_healthy,
        "pending_operations": health.pending_operations_count,
        "failed_jobs": health.failed_jobs_count,
        "alerts": [a.value for a in health.alerts],
    }
```

**Key Changes**:
1. Check role is SUPER_ADMIN
2. Call `get_broker_health()`
3. Returns structured health status
4. Useful for dashboard

---

## 🔍 PATTERN 7: Payment Reconciliation (Background Job)

### Before (Current):
```python
# Not available
```

### After (Production-Ready):
```python
# In a background job (Celery task or APScheduler job)

from app.core.payment_reconciliation import (
    reconcile_payments,
    create_reconciliation_report,
)

async def reconciliation_job():
    """Run every hour to sync pending payments with providers."""
    
    db = get_db_session()  # Get DB connection
    
    # Reconcile all tenants
    tenants = await get_all_active_tenants(db)
    
    for tenant_id in tenants:
        for provider in ["stripe", "paypal", "wise"]:
            try:
                # Get provider-specific client
                provider_client = get_provider_client(provider)
                
                # Run reconciliation
                result = await reconcile_payments(
                    db=db,
                    tenant_id=tenant_id,
                    provider=provider,
                    provider_client=provider_client,
                )
                
                # Create report
                report = await create_reconciliation_report(db, result)
                
                # Log results
                if result.discrepancies_found > 0:
                    logger.warning(f"Reconciliation: {report}")
                else:
                    logger.info(f"Reconciliation OK for {provider}")
                    
            except Exception as e:
                logger.error(f"Reconciliation failed for {tenant_id}/{provider}: {e}")
    
    await db.close()

# Schedule with APScheduler
scheduler.add_job(
    reconciliation_job,
    'interval',
    hours=1,
    id='payment_reconciliation',
)
```

**Key Changes**:
1. Run as background job (not in request/response cycle)
2. Loop through all tenants
3. Call `reconcile_payments()` for each provider
4. Check discrepancies_found
5. Log warnings if issues found

---

## 📚 TESTING PATTERNS

### Test Concurrent Withdrawals (Prevent Double-Spend)
```python
async def test_concurrent_withdrawals_prevented():
    """Two withdrawals for same wallet should only succeed for one."""
    
    wallet = await create_test_wallet(tenant_id, balance=1000)
    
    # Attempt two concurrent withdrawals
    task1 = asyncio.create_task(
        initiate_withdrawal(db, tenant_id, client_id, user_id, 600, ...)
    )
    task2 = asyncio.create_task(
        initiate_withdrawal(db, tenant_id, client_id, user_id, 600, ...)
    )
    
    results = await asyncio.gather(task1, task2, return_exceptions=True)
    
    # One should succeed, one should fail
    assert isinstance(results[0], Exception) or isinstance(results[1], Exception)
    assert not (isinstance(results[0], Exception) and isinstance(results[1], Exception))
```

### Test Duplicate Webhook Handling
```python
async def test_duplicate_deposit_webhook():
    """Same provider event ID should not create duplicate deposit."""
    
    webhook = {
        "provider_id": "evt_123",
        "amount": 100,
        "client_id": client_id,
    }
    
    # Send webhook twice
    result1 = await handle_deposit_webhook(webhook)
    result2 = await handle_deposit_webhook(webhook)
    
    # Both should return success
    assert result1["status"] in ["processed", "already_processed"]
    assert result2["status"] in ["processed", "already_processed"]
    
    # But only one deposit created
    deposits = await get_deposits(tenant_id, client_id)
    assert len(deposits) == 1
```

### Test Tenant Isolation
```python
async def test_tenant_isolation():
    """Broker A should not see Broker B's clients."""
    
    tenant_a = create_tenant("Broker A")
    tenant_b = create_tenant("Broker B")
    
    client_a = create_client(tenant_a)
    client_b = create_client(tenant_b)
    
    # Query as Tenant A
    users_a = await db.execute(
        select(Client).where(build_tenant_filter(tenant_a, Client))
    )
    clients = users_a.scalars().all()
    
    # Should only see client_a
    assert len(clients) == 1
    assert clients[0].id == client_a.id
    assert client_b not in clients
```

---

## 🚀 ROLLOUT CHECKLIST

- [ ] Database migration created and tested
- [ ] All new modules imported and tested individually
- [ ] Tenant isolation added to one endpoint and tested
- [ ] Financial safety integrated with deposits/withdrawals
- [ ] External API calls updated to use retry logic
- [ ] Withdrawal approval workflow integrated
- [ ] Client lifecycle transitions tested
- [ ] Payment reconciliation job scheduled
- [ ] Monitoring/alerting configured
- [ ] Runbooks updated with new endpoints
- [ ] Team trained on production patterns
- [ ] Staged rollout (dev → staging → prod)

---

## 📞 GETTING HELP

1. **Read the implementation guide**: `PRODUCTION_IMPLEMENTATION_GUIDE.md`
2. **Review module docstrings**: Full API docs in each `.py` file
3. **Check patterns above**: Copy-paste and adapt to your endpoint
4. **Run tests**: See testing patterns above
5. **Ask the team**: Production modules are complex - discuss before integrating

---

## ✅ VALIDATION AFTER EACH PHASE

After integrating each pattern, verify:
- [ ] Tests pass
- [ ] No cross-tenant data visible
- [ ] Concurrent operations prevented where needed
- [ ] Retry logic works (simulate timeout)
- [ ] Audit logs created
- [ ] Error handling graceful
- [ ] Performance acceptable
- [ ] No N+1 queries

---

**Last Updated**: 2026-09-01
**Status**: Production modules ready for integration
