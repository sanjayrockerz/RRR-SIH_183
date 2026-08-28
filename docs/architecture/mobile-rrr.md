# Mobile RRR Architecture Boundary

RRR remains a backend-first investigation system. A future mobile client must consume the same versioned API as the investigator web client; it must not access PostgreSQL, Alchemy, Neo4j, Redis, or provider credentials directly.

## Mobile responsibilities

- authenticate an investigator and store only a short-lived access token in the platform secure keystore;
- read cases, wallet intelligence, graph snapshots, patterns, risk, alerts, evidence and timeline through `/api/v1`;
- submit case, wallet, watch and investigator-action commands through the API;
- show explicit `LIVE`, `HISTORICAL`, `DEVELOPMENT_FIXTURE`, `SIMULATED`, `NOT_CONFIGURED` and `DEGRADED` states;
- cache display data for offline review with a visible stale timestamp, never present cached data as live;
- use deep links containing case, wallet, transaction, evidence and pattern IDs.

## Backend boundary

The API remains the system boundary for authorization, validation, audit events, provider calls, evidence provenance, realtime processing and report generation. Mobile push notifications are delivery only: opening a notification must resolve the persisted alert and case from the API.

## Realtime behavior

Mobile receives an alert or refresh signal after the server completes the RRR pipeline. It does not run retracing, risk scoring or graph mutation locally. Development event injection remains restricted to the development API and is visibly marked `SIMULATED`.

## Implemented mobile API foundation

The APK can use the same persisted intelligence workflows through these versioned routes:

- `GET /api/v1/mobile/investigator/feed` — operational summary, cases, alerts and dependency state.
- `GET /api/v1/mobile/cases`, `GET /api/v1/mobile/cases/{case_id}` — case-scoped data.
- `GET /api/v1/mobile/alerts` — persisted alert queue.
- `POST /api/v1/mobile/cases/{case_id}/acknowledge` — audited investigator acknowledgement.
- `POST /api/v1/mobile/cases/{case_id}/watch` — delegates to the server-side realtime watch service.
- `POST /api/v1/mobile/wallet/trace` — delegates to the same trace, persistence, graph, pattern and risk workflow as web.
- `GET /api/v1/realtime/stream?case_id={case_id}` — server-sent case updates; reconnect using `Last-Event-ID` where available.

The native APK remains a separate client implementation. Push delivery, biometric login, offline write queue and device attestation are intentionally not implemented in this repository.
