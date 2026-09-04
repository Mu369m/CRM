# Broker CRM Master Prompt Gap Matrix

Status values: FULL, PARTIAL, MISSING, BUGGY, NOT VERIFIED.
This document records only findings verified against the current repository. It is not a claim that untested integrations work.

## Panel Boundaries

| Surface           | Current state                                                                                                                                                             | Status  | Priority |
| ----------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------- | -------- |
| Master SaaS Owner | Owner routes exist for features, payments, branding, legal CMS and system control; broker directory, plans, health, support access and full governance UI are incomplete. | PARTIAL | P1       |
| Broker Admin      | Core pages exist for clients, leads, finance, KYC, IB, workflows, infrastructure and settings; navigation and several actions remain disconnected or static.              | PARTIAL | P1       |
| Trader Room       | Trader dashboard, profile, KYC, IB, finance and account routes exist with tenant-scoped APIs; complete configurable portal and trading terminal are not present.          | PARTIAL | P1       |

## Verified Findings

| Module                           | Status                 | Evidence / impact                                                                                                                                                                              | Priority |
| -------------------------------- | ---------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------- |
| Tenant-scoped modern broker APIs | FULL/PARTIAL           | Most newer APIs derive tenant_id from authenticated claims and scope queries. Legacy routers use a separate broker_id/get_db path and require reconciliation.                                  | P0       |
| Dynamic custom fields            | PARTIAL                | Definitions/values and tenant uniqueness exist. Disable now preserves values; re-enable reuses the definition. Similar-field warnings and full field visibility/RBAC are missing.              | P0/P1    |
| Custom-field data loss           | FIXED                  | Custom-field DELETE now disables instead of deleting the definition and values. New values on disabled fields are rejected.                                                                    | P0       |
| Owner broadcast target leakage   | FIXED                  | Tenant broadcast endpoint now fails closed and returns only ALL_BROKERS messages because authoritative plan mapping is not available in the owner registry.                                    | P0       |
| Workflow UI authentication       | FIXED                  | Workflow list/create/update/delete requests now send the bearer token required by backend auth and permissions.                                                                                | P1       |
| Owner broadcast save             | FIXED                  | Owner control now calls the real broadcast API and reports failures instead of saving only local React state.                                                                                  | P1       |
| KYC admin upload                 | BUGGY / NOT VERIFIED   | Admin UI submits a hard-coded example.com URL and its file picker/download action is not connected to secure object storage. Do not claim upload or secure download works.                     | P0/P1    |
| KYC route consistency            | BUGGY                  | Frontend uses legacy `/api/v1/broker/kyc-documents`; another tenant-scoped document router uses `/api/v1/broker/documents`. The two models/auth paths must be unified deliberately.            | P0/P1    |
| Owner kill switch and metrics    | MISSING/PARTIAL        | Current UI has local-only lock state and unavailable metrics; no verified backend kill-switch/metrics implementation is registered.                                                            | P0/P1    |
| Frontend role guards             | PARTIAL                | Middleware injects tenant headers but does not authenticate or role-guard admin/owner/trader pages. Backend APIs remain the security source of truth, but UI access boundaries are incomplete. | P0       |
| Broker admin navigation          | PARTIAL                | Shared layout is trader-oriented and does not expose the full broker operational surface.                                                                                                      | P1       |
| Plan/billing engine              | PARTIAL                | Infrastructure entitlement decisions and finance primitives exist; configurable plans, subscriptions, invoices, usage limits, freeze/restore and reconciliation are not verified end-to-end.   | P0/P1    |
| Infrastructure routing           | PARTIAL                | SaaS/external database configuration and encrypted credentials exist; storage connectors are limited and four-way routing/failure migration tests are not verified.                            | P0/P1    |
| Integrations                     | PARTIAL                | Tenant-scoped integration configuration and provider connection testing exist; real MT4/MT5, payment, email, KYC and storage provider coverage is not uniformly verified.                      | P1       |
| Financial idempotency            | PARTIAL                | Idempotency and ledger-related tests/models exist for selected operations; full concurrent withdrawal/payment/reconciliation coverage is not verified.                                         | P0       |
| Audit logging                    | PARTIAL                | Activity/audit services exist and are used by several modules; immutable audit integrity and complete coverage across billing, infrastructure, support and security are not verified.          | P1       |
| Import/export                    | MISSING/PARTIAL        | Basic model/API surfaces exist in places, but safe mapping, preview, background jobs, rollback, large export expiry and complete permission coverage are not verified.                         | P1       |
| Support access                   | MISSING                | Temporary scoped support sessions, approval, expiry, visible banner and revocation are not verified as a complete system.                                                                      | P1       |
| Email engine                     | PARTIAL/MISSING        | Email/provider concepts exist in documentation/code areas, but broker template builder, queue, suppression, delivery logs and provider isolation are not verified end-to-end.                  | P1       |
| AI support                       | MISSING/NOT CONFIGURED | No verified tenant-scoped Trader AI, Broker AI and Master AI implementation is present.                                                                                                        | P2       |
| Trading terminal                 | PARTIAL                | Trading account/control APIs exist; real order execution, server-authoritative permissions, duplicate order protection and reconciliation are not verified.                                    | P0/P1    |
| Responsive/premium UI            | PARTIAL                | Theme and multiple pages exist. Frontend lint has no errors but existing warnings and static/mock-looking surfaces remain.                                                                     | P2       |

## Current Test Evidence

- Backend suite: 25 tests passed when run from the repository root and backend package root.
- Frontend lint: 0 errors; existing warnings remain.
- Touched-file diagnostics: clean after the verified fixes.
- Full production integrations, backup restore, browser/device matrix, cross-tenant attack matrix and live provider tests: NOT VERIFIED.

## Safe Implementation Order

1. Reconcile legacy and modern tenant/auth models for KYC, IB and transaction routers.
2. Add real private object-storage adapter with signed upload/download and tenant ownership checks.
3. Add server-side role/page guards and complete permission enforcement.
4. Centralize plans, subscriptions, entitlements, usage limits and safe freeze/restore.
5. Add verified owner broker/plan/health/support-control surfaces.
6. Add background import/export, reconciliation and idempotent integration jobs.
7. Complete trader-room configuration and real trading-control workflows.
8. Add support access, email, localization, AI and advanced enterprise features only after P0/P1 tests pass.

## Release Gate

Current status: **NO-GO / NOT PRODUCTION-READY**.

Reason: secure KYC file routing, full panel authorization boundaries, legacy tenant-model reconciliation, complete billing lifecycle and several critical integrations are not verified end-to-end. No feature should be reported as complete until its backend, frontend, tenant isolation, permissions, failure path and regression tests pass.
