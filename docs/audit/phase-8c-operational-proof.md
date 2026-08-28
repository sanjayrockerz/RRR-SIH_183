# Phase 8C operational proof — initial diagnostic

Date: 2026-08-27

| DEPENDENCY | EXPECTED | ACTUAL | STATUS | FIX |
|---|---|---|---|---|
| Python backend compilation | `python -m compileall -q app` succeeds | Succeeded | CONNECTED | None |
| FastAPI import | Application imports and routes register | Imported successfully; 99 routes | CONNECTED | None |
| Backend tests | Existing tests pass | `68 passed, 2 skipped` | CONNECTED | Skips are PostgreSQL-gated |
| Frontend tests | Existing tests pass | `1 passed` | CONNECTED | None |
| Frontend production build | `npm run build` succeeds | Succeeded | CONNECTED | None |
| Compose configuration | Four-service local stack validates | `docker compose config --quiet` succeeds | CONNECTED | Docker engine still required to run |
| PostgreSQL | Application can authenticate and migrate | Local Windows service reachable, authentication rejects configured password; `InvalidPasswordError` | DEGRADED | Start Compose PostgreSQL with documented `postgres/postgres`, or provide correct `DATABASE_URL`; do not change production credentials |
| Neo4j | Optional graph backend reports truthful state | Not configured in current process | NOT_CONFIGURED | Start Compose Neo4j and set `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD` |
| Alchemy | Live Ethereum acquisition when key exists | `ALCHEMY_API_KEY` absent | NOT_CONFIGURED | Set key in backend environment only |
| Realtime Alchemy webhook | HMAC-verified live event path | Webhook capability not configured | NOT_CONFIGURED | Set webhook ID/signing key and expose HTTPS callback |
| Development fixture | Deterministic end-to-end acquisition | Provider returns explicit `DEVELOPMENT_FIXTURE` records through TraceService | CONNECTED | Set `BLOCKCHAIN_DATA_MODE=DEVELOPMENT_FIXTURE`; this is never live data |
| Database integrity diagnostics | Counts and orphan checks | Endpoint implemented; cannot query until PostgreSQL authenticates | PARTIAL | Run local Compose stack or correct database credentials |

## Deterministic local configuration

`docker compose up --build` starts PostgreSQL, Neo4j, FastAPI, and Vite. The API service is explicitly configured with `BLOCKCHAIN_DATA_MODE=DEVELOPMENT_FIXTURE` so external credentials are not needed for local workflow testing. To use live Ethereum acquisition, set `BLOCKCHAIN_DATA_MODE=LIVE` and `ALCHEMY_API_KEY` in the backend environment. Live mode does not fall back to fixtures.

The documented fixture root is `0x1111111111111111111111111111111111111111`. Fixture records carry provider `Development Fixture` and raw provenance field `source_mode=DEVELOPMENT_FIXTURE`.

## Known proof boundary

The current machine could not complete database-backed acceptance execution because the Docker Linux engine was unavailable and the existing Windows PostgreSQL password did not match `DATABASE_URL`. Therefore no claim is made that the full case → trace → graph → pattern → risk → realtime → alert → evidence sequence has been runtime-proven on this machine yet.
