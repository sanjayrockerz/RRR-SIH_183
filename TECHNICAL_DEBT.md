# RRR-Realtime Technical Debt & Risk Analysis

This document provides a comprehensive technical audit identifying security risks, performance bottlenecks, database index deficiencies, transaction consistency vulnerabilities, and architectural coupling within the **RRR-Realtime** codebase.

---

## 1. Security & Authentication Vulnerabilities

1. **Opt-In JWT Authentication Default**:
   - **File**: [apps/api/app/auth.py](file:///c:/Users/Rakshan%20M/Downloads/RRR-SIH_183-main%20%281%29/RRR-SIH_183-main/apps/api/app/auth.py#L1-L50)
   - **Risk**: `AUTH_REQUIRED` defaults to `False`. When set to false, all endpoints (including case modifications, webhook replays, and alert escalations) run without bearer token authentication or identity verification.
   - **Impact**: Operational endpoints are exposed to unauthorized access in default deployment configurations.

2. **Missing Role-Based Access Control (RBAC)**:
   - **Risk**: The API does not enforce granular investigator permissions (e.g. `VIEW_ONLY`, `CASE_MANAGER`, `ADMIN`). Any authenticated user can close/reopen cases or modify evidence.

3. **Unauthenticated Operational Webhook & Replay Endpoints**:
   - **File**: [apps/api/app/main.py](file:///c:/Users/Rakshan%20M/Downloads/RRR-SIH_183-main%20%281%29/RRR-SIH_183-main/apps/api/app/main.py#L400-L450)
   - **Risk**: Webhook replay (`POST /api/v1/realtime/replays`) and dead-letter queue management lack IP whitelisting or HMAC signature validation on manual triggers.

---

## 2. Scalability & Performance Bottlenecks

1. **In-Memory NetworkX Graph Rebuilding**:
   - **File**: [apps/api/app/graph_engine.py](file:///c:/Users/Rakshan%20M/Downloads/RRR-SIH_183-main%20%281%29/RRR-SIH_183-main/apps/api/app/graph_engine.py#L20-L80)
   - **Issue**: The NetworkX `MultiDiGraph` is constructed in-memory on every trace execution and pattern analysis request by querying relational `graph_edges` and `normalized_transactions`.
   - **Impact**: Large multi-hop graphs (>10,000 transactions) will cause severe CPU and memory pressure, blocking FastAPI async event loops.

2. **Synchronous Blockchain RPC Pagination**:
   - **File**: [apps/api/app/provider.py](file:///c:/Users/Rakshan%20M/Downloads/RRR-SIH_183-main%20%281%29/RRR-SIH_183-main/apps/api/app/provider.py#L100-L220)
   - **Issue**: Alchemy/TronGrid multi-page transfer fetching loops sequentially page-by-page during deep multi-hop trace requests instead of using parallel chunking or background worker queues.

3. **Synchronous Risk & Pattern Assessment**:
   - **Issue**: Pattern detection and risk assessment execute synchronously within the HTTP request cycle for `POST /api/v1/cases/{id}/traces`.

---

## 3. Database Indexing & Transaction Consistency

1. **Missing Critical Database Indexes**:
   - **Tables**: `cross_chain_links`, `graph_edges`, `case_timeline_events`, `evidence_records`.
   - **Missing Indexes**:
     - `CREATE INDEX idx_cross_chain_links_target ON cross_chain_links (target_address, target_chain);`
     - `CREATE INDEX idx_graph_edges_trace_run ON graph_edges (trace_run_id);`
     - `CREATE INDEX idx_case_timeline_case_created ON case_timeline_events (case_id, created_at DESC);`
   - **Impact**: As transaction volume grows, case loading and cross-chain link queries will degrade to full table scans.

2. **Multi-Table Mutation Transaction Consistency**:
   - **File**: [apps/api/app/persistence.py](file:///c:/Users/Rakshan%20M/Downloads/RRR-SIH_183-main%20%281%29/RRR-SIH_183-main/apps/api/app/persistence.py#L200-L350)
   - **Issue**: In certain multi-step operations (e.g. saving trace runs, updating pattern observations, and recording risk assessments), database operations are split across separate async SQL calls without explicit database transactions (`BEGIN ... COMMIT`).
   - **Risk**: Partial database failures or network disconnections during multi-entity inserts can leave orphan records (e.g. a trace run existing without graph edges).

---

## 4. Webhook & Queue Reliability Issues

1. **Lack of Distributed Background Worker Queue**:
   - **File**: [apps/api/app/realtime_service.py](file:///c:/Users/Rakshan%20M/Downloads/RRR-SIH_183-main%20%281%29/RRR-SIH_183-main/apps/api/app/realtime_service.py#L1-L120)
   - **Issue**: Real-time webhook events are processed directly in FastAPI background tasks or in-memory queues instead of a dedicated distributed worker queue (e.g. Celery / ARQ / Redis).
   - **Risk**: If the API process restarts or crashes during high-volume webhook ingestion, pending retry attempts in memory will be lost.

2. **Webhook Reorg Reconciliation**:
   - **Issue**: Block reorg handling stores reorg observation events, but automatic backward rollback of invalidated graph edges remains a manual action.

---

## 5. Test Suite & Environment Dependencies

1. **HTTP Integration Test Server Dependency**:
   - **File**: [apps/api/tests/test_runtime_open_case.py](file:///c:/Users/Rakshan%20M/Downloads/RRR-SIH_183-main%20%281%29/RRR-SIH_183-main/apps/api/tests/test_runtime_open_case.py#L1-L200)
   - **Issue**: `test_runtime_open_case.py` uses `httpx.Client` pointing to `http://localhost:8000`. When tests are run without a live FastAPI daemon running on port 8000, 4 tests fail and 11 throw connection errors (`ConnectError`).
   - **Remediation Plan**: Refactor runtime open case tests to use FastAPI `TestClient(app)` with ASGI transport so tests execute self-contained without requiring an external server process.

2. **Skipped PostgreSQL Persistence Integration Tests**:
   - **File**: [apps/api/tests/test_postgres_persistence.py](file:///c:/Users/Rakshan%20M/Downloads/RRR-SIH_183-main%20%281%29/RRR-SIH_183-main/apps/api/tests/test_postgres_persistence.py#L1-L50)
   - **Issue**: 3 tests are skipped automatically when a live PostgreSQL container is unavailable in the environment.

---

## 6. Frontend / Backend Coupling & State Management

1. **Monolithic Page Components**:
   - **File**: [apps/investigator-web/src/pages.tsx](file:///c:/Users/Rakshan%20M/Downloads/RRR-SIH_183-main%20%281%29/RRR-SIH_183-main/apps/investigator-web/src/pages.tsx#L1-L800)
   - **Issue**: `pages.tsx` is over 800 lines long, combining UI layout for 9 major workspaces into a single file.
   - **Remediation**: Split `pages.tsx` into modular components under `src/components/workspaces/`.

2. **Polling & Capability State Assumptions**:
   - **Issue**: Webstation dashboard relies on periodic fetch polling instead of WebSocket or Server-Sent Events (SSE) for live event updates.
