# Phase 10 Operational Acceptance

Date: 2026-08-28  
Environment: `docker compose up --build -d` from repository root.  
Scope: existing web workstation and backend connectivity; APK and cross-chain expansion excluded.

## Commands used

Backend canonical command:

```powershell
uvicorn app.main:app --host 0.0.0.0 --port 8000 --app-dir apps/api
```

Full local stack command:

```powershell
docker compose up --build
```

Frontend native command:

```powershell
cd apps/investigator-web
npm run dev
```

## Service results

| Service / check | Result |
|---|---|
| API container | Up, Docker healthy |
| Web container | Up on `http://localhost:5173` |
| PostgreSQL | `CONNECTED`; migrations `READY` |
| Neo4j | `CONNECTED`; browser `http://localhost:7474` returned HTTP 200 |
| Alchemy | `NOT_CONFIGURED` in Compose development-fixture mode; no live claim made |
| Realtime webhook | `NOT_CONFIGURED`; synthetic realtime engine remains explicit development mode |
| `GET /health` | HTTP 200, `status=ok`, persistence PostgreSQL, migrations READY |
| `GET /api/v1/system/status` | HTTP 200, `system=DEGRADED` because optional live integrations are not configured; PostgreSQL/Neo4j connected |
| `GET /api/v1/system/database` | HTTP 200, `CONNECTED` |
| `GET /api/v1/system/integrity` | HTTP 200, `PASS` |
| `GET /api/v1/system/providers` | HTTP 200 with explicit provider states |
| `GET http://localhost:5173` | HTTP 200 |
| `GET http://localhost:5173/api/v1/system/status` | HTTP 200 through the browser-facing path |

## Fresh persisted case demonstration

Seed endpoint returned case ID `2c982730-0fc2-4187-a127-3552c646c12c`.

| Workflow check | Result |
|---|---|
| Case creation / seed | HTTP 200; case persisted in PostgreSQL |
| Case status | `OPEN` |
| Workflow stage | `REPORT_READY` |
| Authoritative summary before realtime | 1 wallet, 9 transactions, 6 graph nodes, 9 graph edges, 3 patterns, risk `GUARDED` 36.0, 1 active watch, 9 evidence, 1 realtime event |
| Open Case record | HTTP 200; title, case ID, wallet, trace loaded |
| Graph | HTTP 200; 6 nodes and 9 edges before realtime |
| Patterns | HTTP 200; 3 persisted observations |
| Risk | HTTP 200; `GUARDED`, score 36.0, evidence-backed factors |
| Realtime synthetic step | HTTP 200; one synthetic event applied |
| Updated summary | 10 transactions, 7 graph nodes, 10 graph edges, 10 evidence records, 2 realtime events |
| Evidence | HTTP 200; 10 persisted records |
| Timeline | HTTP 200; 9 persisted events |
| Report | HTTP 200; 1 persisted report with content hash |
| Integrity | HTTP 200; `PASS`, no orphan warning |

## Automated acceptance

`apps/api/tests/test_operational_acceptance.py` executes create case → wallet → normal investigation orchestration → graph/summary/pattern/risk/watch → synthetic realtime step → updated summary/evidence/timeline/report/integrity.

- Backend full suite: **87 passed, 3 skipped**.
- Full operational acceptance: **1 passed** with `RUN_OPERATIONAL_ACCEPTANCE=1` against Docker.
- Frontend TypeScript/Vite build: **passed**.
- Frontend Vitest suite: **1 passed**.
- Existing open-case smoke flow: **15 passed**.
- Browser acceptance: **passed** after fixing the legacy document click handler; Open Case retained the case context and `FUND FLOW`, `PATTERNS`, `RISK`, `REAL-TIME`, `EVIDENCE`, and `REPORT` resolved to their case-scoped routes without `Request failed`, `API unavailable`, `undefined`, or `404` text.

## Acceptance conclusion

The existing stack starts end-to-end, the browser-facing API path is reachable, cases are loaded from PostgreSQL, Open Case enters the existing case workspace with the authoritative summary loaded first, graph data is persisted and non-empty for the fixture investigation, case-scoped navigation retains the active case context, synthetic realtime updates change persisted metrics, and evidence/timeline/report records are visible through the existing APIs.

Live Alchemy and signed realtime webhook operation remain intentionally `NOT_CONFIGURED` until credentials are supplied. This is an explicit dependency state, not a fabricated live result.
