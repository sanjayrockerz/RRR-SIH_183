# Phase 8A backend connectivity final audit

Audit date: 2026-08-27

## Result

**PARTIAL.** RRR now has a connected investigation intake and explicit system dependency reporting. The repository contains the backend boundaries for persistence, provider retrieval, graph construction, patterns, risk, realtime, alerts, evidence and reports. A complete database-backed end-to-end run could not be proven in this environment because PostgreSQL returned `InvalidPasswordError` and Docker Desktop's Linux engine was unavailable.

## Actually connected in code

- Case creation and PostgreSQL case registry.
- Wallet association and optional transaction reference association.
- Chain-aware trace request through the provider registry.
- Provider normalization, trace persistence, graph/evidence persistence and optional Neo4j projection.
- Automatic pattern analysis and deterministic risk assessment after connected intake trace.
- Persisted evidence ledger and integrity manifest APIs.
- Persisted reports, alerts, timeline and change-set APIs.
- Realtime watch processing, simulated event injection, deduplication, application, evidence, graph-edge, timeline, risk/pattern hooks and alert candidate creation.
- Persisted case workflow stages and stage history through `workflow_stage`, `case_workflow_events`, and `GET /api/v1/cases/{case_id}/workflow`.
- Provider health probes for configured Alchemy and TronGrid adapters; failures are reported as `DEGRADED` rather than green configuration-only status.
- Cross-workspace case tabs and dashboard metric navigation.
- Dependency health endpoints:
  - `GET /api/v1/system/status`
  - `GET /api/v1/system/providers`
  - `GET /api/v1/system/dependencies`

## Exact workflow

1. `POST /api/v1/cases`
2. `POST /api/v1/cases/{case_id}/wallets`
3. Optional `POST /api/v1/cases/{case_id}/transactions`
4. `POST /api/v1/cases/{case_id}/traces`
5. `POST /api/v1/cases/{case_id}/patterns/analyze`
6. `POST /api/v1/cases/{case_id}/risk/assess`
7. `GET /api/v1/cases/{case_id}/workflow`
8. `POST /api/v1/cases/{case_id}/watches` with `source=SIMULATED` for local testing, or live Alchemy configuration
9. `POST /api/v1/realtime/simulated/events` or signed Alchemy webhook
10. Read case graph, patterns, risk, alerts, evidence, timeline, changes and reports.

## Status classification

| Capability | Current status | Proof/condition |
|---|---|---|
| FastAPI | CONNECTED | API starts and health endpoint responds |
| PostgreSQL | UNAVAILABLE | Startup and system probe report `InvalidPasswordError` |
| Alchemy historical | NOT_CONFIGURED | `ALCHEMY_API_KEY` is empty |
| Alchemy realtime | NOT_CONFIGURED | API key, webhook ID and signing key are empty |
| Local simulated realtime | SIMULATED | Unit-tested watch branch and UI event control; database runtime still required |
| Neo4j | NOT_CONFIGURED | URI/password are not configured and Docker is unavailable |
| TronGrid | NOT_CONFIGURED | `TRONGRID_API_KEY` is empty |
| OFAC/sanctions | UNAVAILABLE while DB is down; NOT_CONFIGURED when DB has no records | Persisted dataset boundary exists; no live feed is bundled |
| Threat intelligence | UNAVAILABLE while DB is down; NOT_CONFIGURED when DB has no sources | Persisted source boundary exists; no live provider is bundled |
| Authentication | PARTIAL | JWT verification boundary exists; case-level authorization is not implemented |
| Reports/export | PARTIAL | Persisted report snapshots exist; signed/authenticated export is not implemented |

## Required environment variables

- `DATABASE_URL`
- `DATABASE_AUTO_MIGRATE`
- `ALCHEMY_API_KEY`
- `ALCHEMY_NETWORK`
- `ALCHEMY_WEBHOOK_ID`
- `ALCHEMY_WEBHOOK_SIGNING_KEY`
- `TRONGRID_API_KEY`
- `NEO4J_URI`
- `NEO4J_USERNAME`
- `NEO4J_PASSWORD`
- `AUTH_REQUIRED`
- `AUTH_JWT_PUBLIC_KEY`
- `AUTH_JWT_ISSUER`
- `AUTH_JWT_AUDIENCE`

See `.env.example` for defaults and the explicit local-development configuration boundary.

## Test results

- Backend: `68 passed, 2 skipped`.
- Frontend Vitest: `1 passed`.
- Frontend TypeScript/Vite production build: passed.
- Python compilation: passed.
- API smoke: health responded `degraded`; system status responded HTTP 200 with `system=UNAVAILABLE`, PostgreSQL `UNAVAILABLE`, and configured dependencies accurately classified.

## Not proven yet

- Database state changes across the full case → trace → realtime → alert → report workflow.
- Live Alchemy retrieval and signed webhook delivery.
- Neo4j projection/query runtime.
- Browser-level click-through validation.
- Production authentication, authorization, secret management, queue workers, notifications and signed evidence export.
