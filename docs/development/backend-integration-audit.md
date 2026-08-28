# Backend integration audit

Updated: 2026-08-26

## Runtime architecture

The intended request path is `React → FastAPI → application services → repository → PostgreSQL`, with provider adapters feeding normalized observations into the trace, pattern, risk, realtime, and cross-chain services. The API has no in-memory fallback when PostgreSQL is unavailable.

## Operational inventory

| Area | Current state | Persistence | UI state |
|---|---|---|---|
| Case create/read | Implemented | PostgreSQL | Connected through intake |
| Case list/update/close/reopen | Implemented in Phase 9 | PostgreSQL | List API ready; lifecycle controls pending UI wiring |
| Wallet intake | Implemented | PostgreSQL, deduplicated by chain/address | Connected through intake |
| Historical Ethereum data | Implemented | Normalized transactions/transfers | Connected through trace flow |
| Graph and bounded trace | Implemented | Trace runs, graph edges, evidence | Connected through graph inspector |
| Entity attribution | Implemented | Attribution catalog and provenance | API-connected; dedicated UI remains capability surface |
| Behavioral patterns | Implemented | Pattern observations/evidence links | Connected through Patterns workspace |
| Risk posture | Implemented | Immutable assessments/factors/deltas | Connected through Risk workspace |
| Realtime retracing | Boundary implemented | Events, watches, timeline, alerts | Explicitly NOT CONFIGURED without Alchemy webhook settings |
| Cross-chain intelligence | Boundary/partial runtime | Cross-chain observations, links, traces | Explicit capability states; Tron/bridges require configuration |
| Reports | Boundary only | No report persistence/service yet | Capability surface |
| Authentication/SSO | Not implemented | N/A | No fake identity claims |

## Startup and database readiness

The API now remains available when PostgreSQL is unavailable, but data routes fail closed with HTTP 503. `GET /health` returns `degraded` and `GET /api/v1/system/status` exposes database and migration state. On a reachable database, startup applies ordered SQL migrations once and records them in `schema_migrations`.

Migration `009_backend_integration.sql` adds case lifecycle metadata and operational indexes.

## Current validation

- Python compilation: passed.
- FastAPI import and route registration: passed; 60 routes.
- Backend tests: 30 passed, 2 skipped.
- Local API startup with unavailable PostgreSQL: passed; explicit degraded state observed.
- PostgreSQL runtime validation: blocked by the local server rejecting the configured `postgres` password.

## Known integration gaps

- Case list and lifecycle controls need to be surfaced in the React workspace.
- Entity, evidence, alert, timeline, ledger, and report workspaces have different levels of backend connectivity; they must not display fixture data as live data.
- PostgreSQL credentials/container availability must be fixed before end-to-end persistence can be validated.
