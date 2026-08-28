# Operational gap analysis

Date: 2026-08-27

This audit covers the current RRR repository before the next implementation slice. Statuses describe verified runtime behavior, not the presence of source files.

| Capability | Current classification | Priority | Finding |
|---|---|---:|---|
| Frontend routing and shell | REAL_LOCAL | P1 | Routes render and call the API, but several legacy components remain in source. |
| Case intake/list/detail | REAL_CONNECTED | P0 | PostgreSQL-backed and verified through Compose. |
| Wallet intelligence | PARTIALLY_CONNECTED | P1 | Persisted counts/observations work; custody, balance, threat and sanctions fields are not fully surfaced. |
| Blockchain acquisition | FIXTURE_ONLY / credential-gated LIVE | P0 | Development fixture uses the shared provider interface; Alchemy requires `ALCHEMY_API_KEY`. |
| Transaction normalization/persistence | REAL_CONNECTED | P0 | Provider provenance, deduplication and evidence are persisted. |
| NetworkX graph | REAL_CONNECTED | P0 | Trace graph is persisted and rendered; layout/readability was repaired. |
| Neo4j projection | REAL_CONNECTED when configured | P1 | Compose Neo4j projection is connected and optional; PostgreSQL remains canonical. |
| Pattern engine | REAL_CONNECTED | P1 | Trace-triggered pattern persistence is verified. |
| Risk engine | REAL_CONNECTED | P1 | Deterministic risk assessment is persisted; realtime risk requires a valid prior trace. |
| Realtime/RRR | PARTIALLY_CONNECTED | P0 | Simulated event path is connected; automatic expansion and full recursive retrace need deeper proof. |
| Entity/VASP attribution | PARTIALLY_CONNECTED | P1 | Provider-independent catalog boundary exists; no commercial dataset is configured. |
| OFAC/sanctions | NOT_CONFIGURED | P1 | Schema and screening boundary exist; no OFAC dataset is installed. |
| Threat intelligence | NOT_CONFIGURED | P1 | Schema and provider boundary exist; no external source is configured. |
| Evidence ledger | PARTIALLY_CONNECTED | P1 | Evidence provenance and ledger APIs exist; investigator-readable presentation and verification need completion. |
| Reports | REAL_CONNECTED | P1 | Reports are generated from persisted case data; VASP action workflow is absent. |
| Alerts | REAL_CONNECTED | P1 | Persisted alert queue and review operations exist; alert generation depends on risk delta. |
| Cross-chain | PARTIALLY_CONNECTED | P2 | Ethereum/Tron data model and correlation boundary exist; live multi-chain provider coverage is limited. |
| Authentication/authorization | PARTIALLY_CONNECTED | P0 | JWT boundary exists but is disabled in local development. |
| ML/AI | NOT_CONFIGURED | P2 | No AI investigation provider is implemented/configured. |
| Mobile/API readiness | REAL_LOCAL | P2 | REST APIs are reusable by mobile; push registration and mobile-specific auth contracts remain. |

## P0 blockers

- Startup must use the Compose stack or a valid `DATABASE_URL`; host processes can mask the correct API.
- The API migration runner and realtime pipeline needed runtime fixes discovered during live testing.
- Live providers, OFAC, threat intelligence and notifications require external configuration.

## P1/P2/P3 backlog

P1: complete investigator-readable evidence and transaction workspaces, automatic watch expansion, recursive retrace proof, and authenticated production operations. P2: richer entity/sanctions/threat intelligence and mobile contracts. P3: visual polish after data semantics are complete.
