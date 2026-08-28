# BYODB (Bring Your Own Database) Safety Guarantees

## Connection Validation
- All tenant DB URLs are validated for PostgreSQL async format
- First connection is tested with `SELECT 1` before caching
- Mismatched URLs raise `ConnectionError` immediately

## Cache Management
- LRU engine cache limited to 100 tenants
- Evicted engines are disposed properly
- Cache coherency via asyncio locks

## Migrations
- Alembic upgrades run before API startup
- Migration failure halts API (prevents partial DB state)
- Each broker can manage their own migration state

## Tenant Isolation
- JWT `tenant_id` claims must match requested `X-Tenant-ID` header
- Host validation ensures subdomain/custom domain matches claims
- Database sessions are scoped per-tenant

## Risk of Misconfiguration
- Invalid encrypted DB URL: ConnectionError on first access
- Network outage to tenant DB: Request fails with 503
- Insufficient DB permissions: Connection succeeds but queries fail (add audit logging)
