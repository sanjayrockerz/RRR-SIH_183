# Operational Readiness — Phase 8D

Validated against the local Docker stack on 2026-08-27.

## What works now

- `POST /api/v1/dev/seed-case` executes a PostgreSQL-backed development investigation: case, wallet, fixture acquisition, normalized transactions, trace, graph projection, patterns, risk, watch, realtime processing and report.
- `GET /api/v1/system/database/integrity` verifies persisted counts and orphan relationships.
- PostgreSQL and Neo4j health are reported independently. Alchemy, TronGrid, realtime provider, OFAC and threat intelligence remain explicit `NOT_CONFIGURED` without credentials.
- The graph is derived from trace observations and the UI now lays out actual hops and uses readable semantic colors for root, wallet, contract and risk-linked observations.
- Evidence is rendered as provenance cards with friendly type labels, source, capture time, chain, transaction and metadata rather than raw UUID-only rows.
- The web production build completes successfully.

## Runtime proof

Seed result observed:

| Stage | Observed result |
|---|---:|
| fixture graph nodes | 6 |
| fixture graph edges | 8 |
| detected patterns | 3 |
| risk score | 36 |
| realtime pipeline results | 3 |
| database orphan records | 0 |

The development seed’s realtime event did not increase risk in this run, so no alert was fabricated. Alert creation remains data-dependent and must be demonstrated with an event that produces a real risk delta.

## Status matrix

| Capability | Backend | Database | UI | Provider | Status |
|---|---|---|---|---|---|
| Case and wallet persistence | Connected | PostgreSQL | Connected | n/a | COMPLETE |
| Fixture acquisition | Connected | PostgreSQL provenance | Mode visible | Development Fixture | DEVELOPMENT_FIXTURE |
| Alchemy acquisition | Connected by configuration | PostgreSQL | Status visible | Requires `ALCHEMY_API_KEY` | NOT_CONFIGURED locally |
| Trace and graph | Connected | PostgreSQL; Neo4j projection | Readable graph | NetworkX/Neo4j | COMPLETE locally |
| Pattern and risk | Connected | Persisted records | Existing workspaces | Internal engines | COMPLETE locally |
| Evidence | Connected | Persisted provenance | Readable evidence page | Provider-dependent | COMPLETE locally |
| Realtime watch/event loop | Connected | Persisted events/timeline | Existing realtime workspace | Simulated locally | SIMULATED locally |
| Alert escalation | Implemented | Persisted | API/UI available | Requires risk delta | PARTIAL |
| Entity attribution | Boundary and curated support | Persisted | Workspace available | Commercial providers optional | PARTIAL |
| OFAC screening | Boundary | Persisted when configured | Status available | Requires dataset | NOT_CONFIGURED locally |
| Reports | Connected | Persisted report | Report workspace | n/a | COMPLETE locally |
| Native mobile | API boundary documented | Same backend | Not implemented | n/a | NOT_CONFIGURED |

## Required local commands

```text
docker compose up --build -d
POST http://localhost:8000/api/v1/dev/seed-case
GET  http://localhost:8000/api/v1/system/status
GET  http://localhost:8000/api/v1/system/database/integrity
```

Local services: web `http://localhost:5173`, API `http://localhost:8000`, PostgreSQL host port `5433`, Neo4j browser `http://localhost:7474`.

## Checks

- Python compilation: PASS (`python -m compileall -q app`)
- API tests: PASS (34 tests)
- Web production build: PASS (`tsc -b && vite build`)
- Docker Compose stack: PASS; postgres, neo4j, api and web healthy/running
- Database integrity: PASS; orphan total `0`
- Live Alchemy: NOT_CONFIGURED because no `ALCHEMY_API_KEY` was supplied
