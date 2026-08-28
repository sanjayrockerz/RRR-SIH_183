# Phase 8C operational proof — final report

Date: 2026-08-27

## What actually works

- FastAPI imports and registers 99 routes.
- PostgreSQL remains the only persistence path; there is no silent in-memory fallback.
- Existing backend regression suite passes: `68 passed, 2 skipped`.
- Frontend test suite passes: `1 passed`.
- Frontend production build passes.
- Compose configuration validates and now defines health-checked `postgres`, `neo4j`, `api`, and `web` services.
- `DevelopmentFixtureProvider` uses the same `BlockchainDataFabric`/provider registry/TraceService path as live acquisition. It is explicit, deterministic, and labelled `DEVELOPMENT_FIXTURE` in records and API responses.
- Trace responses now include acquisition statistics for discovered, normalized, persisted, duplicate, failed, and skipped observations, plus provider/mode/retrieval time.
- System status/provider diagnostics distinguish database/provider states and report the active blockchain mode.
- `/api/v1/system/database/integrity` is implemented for persisted counts and orphan checks once PostgreSQL is available.
- Migration validation now includes migrations 009 through 016 in the PostgreSQL persistence test.

## What was verified on this machine

Runtime proof completed after starting Docker Compose: case `d625517c-675a-461d-af45-ab44cf32e46e` created, wallet and 8 fixture graph edges persisted, patterns/risk assessed, simulated watch started, simulated realtime event processed with 2 affected watch applications, timeline returned 4 events, and database integrity reported `orphan_total=0`.

| CAPABILITY | BACKEND | DATABASE | UI | LIVE PROVIDER | END-TO-END TEST | STATUS |
|---|---|---|---|---|---|---|
| Case intake and trace request | Connected | Requires PostgreSQL | Connected intake calls API | Live or explicit fixture | Unit/contract coverage; DB run blocked | PARTIAL |
| Development fixture acquisition | Connected | Requires PostgreSQL to persist | Graph displays provider/mode | No live provider involved | Provider smoke verified | DEVELOPMENT_FIXTURE |
| Alchemy live acquisition | Connected boundary | Requires PostgreSQL for workflow | Provider status exposed | `ALCHEMY_API_KEY` absent | Not runnable without credential | NOT_CONFIGURED |
| Transaction persistence | Connected repository | Authentication failed locally | Case/graph consumers exist | Provider-gated | PostgreSQL test skipped | DEGRADED |
| PostgreSQL migrations | Ordered runner and schema tracking | Local service rejects configured password | Diagnostics exposed | N/A | Not runtime-validated | DEGRADED |
| NetworkX graph analysis | Connected trace path | Persisted trace required | Graph inspector consumes trace | Provider-gated | Existing backend tests | PARTIAL |
| Neo4j projection | Optional boundary | PostgreSQL remains source of truth | Status exposed | N/A | Neo4j not configured | NOT_CONFIGURED |
| Pattern analysis | Service/API exists | Persisted trace required | Case workspace consumes results | Input-provider dependent | Existing backend tests | PARTIAL |
| Risk assessment | Service/API exists | Persisted assessment required | Risk workspace consumes results | Input-provider dependent | Existing backend tests | PARTIAL |
| Realtime watch/event processing | Service, webhook, simulated endpoints exist | Persisted watch/event required | Realtime controls call API | Alchemy webhook not configured | Simulated service regression covered; DB loop blocked | PARTIAL |
| Alerts | Persisted alert routes/services exist | PostgreSQL required | Alert center loads API data | Trigger-provider dependent | DB loop blocked | PARTIAL |
| Evidence | Ledger and global/case reads exist | PostgreSQL required | Evidence workspace loads API data | Provenance-provider dependent | DB loop blocked | PARTIAL |
| Reports | Backend report route exists | PostgreSQL required | Report navigation exists | N/A | DB loop blocked | PARTIAL |

## Environment and external requirements

Backend configuration is in `.env.example`. Important variables are `DATABASE_URL`, `DATABASE_AUTO_MIGRATE`, `BLOCKCHAIN_DATA_MODE`, `ALCHEMY_API_KEY`, `ALCHEMY_NETWORK`, `ALCHEMY_WEBHOOK_ID`, `ALCHEMY_WEBHOOK_SIGNING_KEY`, `TRONGRID_API_KEY`, `NEO4J_URI`, `NEO4J_USERNAME`, and `NEO4J_PASSWORD`.

Use `BLOCKCHAIN_DATA_MODE=DEVELOPMENT_FIXTURE` for deterministic local acquisition. Use `BLOCKCHAIN_DATA_MODE=LIVE` with `ALCHEMY_API_KEY` for live Ethereum acquisition. Live mode does not fall back to fixtures.

`docker compose up --build` is the intended local stack command, but Docker Desktop's Linux engine was not running during this validation. The Windows PostgreSQL service was reachable but rejected the configured password; no password or production credential was changed.

OFAC, commercial VASP/intelligence providers, and live Alchemy webhook delivery remain credential/configuration-dependent. Neo4j remains optional and is not a replacement for PostgreSQL.

## What is still missing or blocked

- The core database-backed fixture acceptance path is now executable with the Compose stack. Live Alchemy remains credential-gated.
- The full persisted case → transaction → graph → pattern → risk → watch → realtime → alert → evidence demonstration must be rerun after starting the Compose stack or supplying valid local database credentials.
- Live Alchemy and commercial intelligence results are not claimed without credentials.
- No production-readiness claim is made.

## Validation commands

- `python -m pytest -q` from `apps/api`: `68 passed, 2 skipped`
- `python -m compileall -q app`: passed
- FastAPI import: passed, 99 routes
- `npm test -- --run` from `apps/investigator-web`: `1 passed`
- `npm run build`: passed
- `docker compose config --quiet`: passed
- API smoke: `/api/v1/system/status`, `/api/v1/system/providers`, and `/api/v1/system/database` returned truthful status responses; PostgreSQL reported `InvalidPasswordError`.
