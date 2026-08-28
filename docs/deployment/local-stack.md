# Local stack

The repository provides PostgreSQL, Redis and Neo4j services in `docker-compose.yml`. Copy `.env.example` to `.env`, set a database URL matching the running PostgreSQL credentials, and configure provider keys only when needed.

Start dependencies with `docker compose up -d postgres redis neo4j`, then run the API from `apps/api` with `python -m uvicorn app.main:app --reload --port 8000` and the frontend from `apps/investigator-web` with `npm run dev`.

Verify `/health`, `/api/v1/system/status`, `/api/v1/system/database` and `/api/v1/system/providers`. The API may start degraded, but case data is never stored in an in-memory fallback.
