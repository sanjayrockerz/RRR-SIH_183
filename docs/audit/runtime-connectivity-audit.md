# Runtime Connectivity Audit

Date: 2026-08-28  
Scope: existing local RRR investigator stack; no APK, cross-chain, or UI redesign work.

## Runtime topology

| Component | Entrypoint / URL | Configuration | Dependency | Failure behavior |
|---|---|---|---|---|
| FastAPI | `uvicorn app.main:app --host 0.0.0.0 --port 8000 --app-dir apps/api` | root `.env`; `API_ORIGIN`, `BLOCKCHAIN_DATA_MODE`, `DATABASE_URL`, `NEO4J_*`, provider keys | PostgreSQL required for persisted case APIs; Neo4j optional projection; blockchain providers capability-gated | Lifespan records PostgreSQL/Neo4j availability; process remains alive; health reports degraded when PostgreSQL is unavailable |
| PostgreSQL | Docker `postgres:16-alpine`, host `5433`, Compose service `postgres:5432` | `DATABASE_URL`; Compose API overrides to `postgres` hostname | Ordered SQL migrations under `infrastructure/postgres` | `PostgresCaseRepository.connect()` sets `UNAVAILABLE`, preserves API process, and case endpoints return structured 503 |
| Neo4j | Docker `neo4j:5-community`, `localhost:7687`, browser `localhost:7474` | `NEO4J_URI`, username, password, database | Graph projection/query only; PostgreSQL remains source of truth | Connect failure is represented as unavailable/not configured; trace persistence does not depend on Neo4j query availability |
| Web | Vite dev server `http://localhost:5173` | `VITE_API_BASE_URL`; optional `VITE_API_TARGET` for Vite proxy | FastAPI | Canonical API client reports API offline, timeout, HTTP, database, or invalid-response categories |

## Backend request map

The backend is registered in `apps/api/app/main.py` and uses shared service/repository objects. The authoritative case flow is:

`POST /api/v1/cases` → `POST /api/v1/cases/{case_id}/wallets` → `POST /api/v1/cases/{case_id}/investigate` (normal full orchestration) or `/traces` (lower-level trace) → `GET /api/v1/cases/{case_id}/summary` → `GET /api/v1/cases/{case_id}/graph` → patterns/risk/watches/realtime/evidence/timeline/reports.

Health and diagnostics:

- `GET /health`: process and PostgreSQL readiness (`ok`/`degraded`), migration status.
- `GET /api/v1/system/status`: PostgreSQL, Neo4j, Alchemy, TronGrid, realtime, OFAC, and threat-intelligence states.
- `GET /api/v1/system/dependencies`: same dependency contract.
- `GET /api/v1/system/database`: pool, migration, and safe database target diagnostics.
- `GET /api/v1/system/integrity`: orphan-record/integrity summary.
- `GET /api/v1/system/providers`: provider capability, reachability, network, and latency details.

Status values observed in code are `CONNECTED`, `DEGRADED`, `UNAVAILABLE`, `NOT_CONFIGURED`, and `SIMULATED`; development fixture mode is explicitly returned as `DEVELOPMENT_FIXTURE`/`SIMULATED`, never as live provider data.

## Frontend request map

`apps/investigator-web/src/api.ts` is the canonical request boundary. All ordinary HTTP requests use `API_BASE`, `apiUrl()`, a 15-second timeout, JSON parsing, request IDs, and structured `ApiError` categories.

| UI surface | Requests | Case context |
|---|---|---|
| Operational dashboard | dashboard summary, system status, cases, alerts, providers | global |
| Cases registry | `GET /api/v1/cases` | global; persisted PostgreSQL list |
| Open Case | summary first, case, graph, operational state | active case retained in React state and `rrr_active_case_id` |
| Overview | operational state, workflow, related cases | `case_id` passed to every child |
| Graph | persisted `GET /api/v1/cases/{case_id}/graph`, graph layout, risk/attribution | case scoped |
| Transactions | `/transactions` | case scoped |
| Patterns | analyze, list, summary | case + trace scoped |
| Risk | assessment, delta, factors, alerts | case scoped |
| Realtime | watches, timeline, changes, alerts, capabilities | case scoped |
| Evidence | evidence and ledger/manifest endpoints | case scoped |
| Reports | list/create report | case scoped |
| Diagnostics | providers, database, integrity, sanctions, dashboard | global |

The realtime `EventSource` is the only browser streaming primitive; its URL is produced by the shared `apiUrl()` helper. No second raw `fetch()` client remains in `pages.tsx`.

## Findings and fixes

1. The previous Open Case seed path failed while persisting acquisition metadata because nested datetimes reached `json.dumps()`. Trace persistence now normalizes remaining JSON values at the PostgreSQL boundary.
2. The seed path awaited synchronous attribution resolution. The incorrect await was removed.
3. Report generation used removed `RiskFactor.score_delta` and `AcquisitionStatistics.duration_ms` fields. It now uses `contribution` and the available `retrieved_at` value.
4. The frontend API default was relative/empty, which made native Vite and Docker behavior dependent on proxy context. The local default is now `http://localhost:8000`; `VITE_API_BASE_URL` remains supported.
5. `pages.tsx` had a second raw HTTP client and swallowed diagnostics failures into empty values. It now uses the canonical client; case registry distinguishes loading, backend unavailable, and database-connected empty states.
6. Open Case previously navigated directly to Graph after loading only the case record. It now loads the authoritative summary first, loads persisted graph data when present, preserves the active case ID, and enters the existing Overview workspace.

## CORS and startup

FastAPI allows `settings.api_origin` plus `http://localhost:5173`, with all methods/headers and no wildcard credential mode. The Compose API uses internal service DNS for PostgreSQL/Neo4j; the browser uses published host ports. Compose health checks wait for PostgreSQL and Neo4j before starting API, and web waits for API health.

Canonical commands from repository root:

```powershell
docker compose up --build
```

Native API:

```powershell
\.venv\Scripts\Activate.ps1
uvicorn app.main:app --host 0.0.0.0 --port 8000 --app-dir apps/api
```

Native web (second terminal):

```powershell
cd apps/investigator-web
npm install
npm run dev
```

## Remaining boundaries

Alchemy/TronGrid/realtime are `NOT_CONFIGURED` without their credentials. Development fixture/synthetic paths are explicit and labelled. Cross-chain routes remain present as existing capability surfaces but are not expanded by this audit. No APK or new frontend architecture is introduced.
