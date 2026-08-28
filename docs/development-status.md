# Development status

## Phase 8C — Operational proof

Status: PARTIAL — explicit development fixture path and diagnostic reporting are implemented; live database/provider execution still requires local dependency availability.

Implemented: deterministic `DEVELOPMENT_FIXTURE` provider through the same trace/provider abstraction, fixture mode shown in system/provider responses, deterministic Compose `postgres`, `neo4j`, `api`, and `web` services with health checks, database integrity endpoint, migration test coverage including migration 016, and operational diagnostic reports under `docs/audit/`.

Blocked locally: the Windows PostgreSQL service accepts connections but rejects the configured password (`InvalidPasswordError`); Docker Desktop's Linux engine is not running. No credentials were changed.

## Principal architecture audit — Phase A

Status: COMPLETE — audit and roadmap gate.

Added:

- `docs/architecture/system-audit.md`
- `docs/architecture/production-readiness.md`
- `docs/architecture/target-runtime.md`
- `docs/implementation-roadmap.md`

The audit confirms that the historical Ethereum investigation path is real and persisted, while Neo4j, cyber-intelligence providers, sanctions, authentication/RBAC, reporting, and production export controls remain future implementation slices. No speculative provider or graph integration was added during this audit gate.

## Phase B — Backend connection cleanup

Status: IN PROGRESS.

Implemented in the current slice:

- `GET /api/v1/dashboard/summary` backed by PostgreSQL aggregates.
- Dashboard UI now consumes persisted case, wallet, alert, entity, transaction, and watch counts instead of hardcoded metrics.
- Dashboard shows explicit unavailable/error state when PostgreSQL cannot serve aggregates.
- FastAPI runtime smoke test confirmed the route returns HTTP 503 while storage is unavailable; no fake zeros are returned.
- `GET /api/v1/cases/{case_id}/evidence` is now a repository-backed evidence read path.
- Entity catalog and global alert queue workspaces now consume backend APIs and show empty/error states without fixture data.
- Added `GET /api/v1/alerts` for the persisted alert queue.

Next: add API contract tests for UI-used routes, request IDs/error envelopes, and complete report/timeline workspace connectivity.

## Phase C — Neo4j relationship projection

Status: IMPLEMENTED BOUNDARY / NOT CONFIGURED LOCALLY.

Implemented:

- Optional Neo4j driver/client with explicit `SUPPORTED`, `NOT_CONFIGURED`, and `UNSUPPORTED` state.
- Idempotent projection modules under `apps/api/app/graph/`.
- Deterministic chain/transaction/edge identifiers.
- Case, wallet, transaction, chain, and evidence graph projection with transaction/evidence properties preserved.
- Bounded neighbor and shortest-path query endpoints:
  - `GET /api/v1/graph/status`
  - `POST /api/v1/graph/{case_id}/project`
  - `GET /api/v1/graph/{case_id}/neighbors`
  - `GET /api/v1/graph/{case_id}/shortest-path`
- New traces attempt projection after PostgreSQL persistence; projection failure does not invalidate the canonical trace.
- Neo4j Docker Compose service and environment configuration.

Known limitations: Neo4j is not configured in the current environment, the incremental projection path is not runtime-validated locally, and broader graph query families remain future slices. PostgreSQL remains the source of truth and NetworkX remains the bounded analysis engine.

Incremental projection update: `GraphProjectionService.project_incremental` now accepts the existing canonical realtime event and projects a bounded, evidence-linked edge when Neo4j is configured. Projection remains optional and non-authoritative; the local environment still has no Neo4j credentials/runtime validation.

## Phase D — Provider operations

Status: IMPLEMENTED BOUNDARY / CREDENTIAL-GATED.

Implemented:

- Provider registry selects Alchemy Ethereum or TronGrid by requested chain without coupling TraceService to a vendor.
- `GET /api/v1/providers` exposes provider, chain, capability, and configuration state.
- Provider timeouts and bounded retries for transient HTTP/network/server/rate-limit failures are environment-configurable.
- System operations UI renders registered provider states without hardcoded “connected” claims.
- Existing provider pagination, normalization, and capability tests remain green.

Known limitations: no Etherscan fallback adapter is enabled, provider health is configuration/capability state rather than a continuous telemetry service, and no provider secret is exposed to the frontend.

## Phase 9 — End-to-end backend integration

Status: PARTIAL — integration foundation implemented; PostgreSQL runtime validation pending local credentials.

Implemented in this slice:

- API remains available in explicit `degraded` mode when PostgreSQL is unavailable; no in-memory fallback is used.
- Ordered startup migration runner with `schema_migrations` tracking and `DATABASE_AUTO_MIGRATE` configuration.
- `GET /api/v1/system/status` operational state endpoint.
- Persistent case registry with `GET /api/v1/cases`.
- Case update, close, and reopen endpoints behind the repository boundary.
- Case lifecycle metadata migration `009_backend_integration.sql`.
- React Cases workspace now loads the persisted case index and reports backend errors explicitly.
- Backend integration audit at `docs/development/backend-integration-audit.md`.

Validation: Python compilation, FastAPI import, 44 backend tests passed/2 skipped, frontend tests passed, frontend production build passed. PostgreSQL integration remains blocked by the local Docker Linux engine/database runtime.

Cybersecurity maturity audit: `docs/audit/rrr-current-state.md`, `docs/audit/provider-comparison.md`, and `docs/architecture/cybersecurity-intelligence.md` document current capability claims, provider boundaries, and P0/P1 hardening priorities. The frontend now uses `/api/v1/system/status` so PostgreSQL degradation is not presented as an operational API state.

## Phase E - Entity/VASP intelligence boundary

Status: IN PROGRESS - provenance and provider boundary implemented; commercial intelligence is not connected.

Implemented: versionable attribution-source records through migration `010_entity_provenance.sql`, entity-specific attribution and source read APIs, and an `EntityIntelligenceProvider` boundary with a persisted curated-catalog adapter.

Known limitations: no commercial provider adapter or automatic dataset import is enabled. Attribution remains limited to records explicitly persisted in the curated catalog and does not establish ownership or criminal involvement.

Next: Phase F - Cyber intelligence and sanctions, beginning with versioned indicator/sanctions models and explicit configured-source states.

## Phase F - Cyber intelligence and sanctions foundation

Status: IMPLEMENTED BOUNDARY / SOURCE-CONFIGURED.

Implemented: versioned cyber-intelligence sources, threat-indicator and sanctions-record models, contract-security finding storage, provider-independent screening boundary, exact chain-aware address screening, persisted case screening runs, and explicit `NOT_CONFIGURED`, `NO_MATCH`, and `DIRECT_MATCH` outcomes.

Known limitations: no live OFAC/commercial feed is bundled or connected, no indirect/fuzzy screening is performed, contract findings have storage/API boundaries only, and screening results are investigative source results rather than legal determinations.

Documentation: `docs/architecture/threat-intelligence.md`, `docs/architecture/sanctions-screening.md`, `docs/architecture/contract-security.md`, and ADR `0009-cyber-intelligence-source-boundary.md`.

## Phase G - Realtime operations hardening

Status: IMPLEMENTED BOUNDARY / MANUAL REPLAY.

Implemented: durable processing attempts, retry-pending and dead-letter states, bounded attempt configuration, failure queue API, explicit replay API, idempotent retry handling, and documented reorg behavior.

Known limitations: no background queue worker, exponential scheduler, dead-letter notification channel, confirmation-depth reconciliation, or production authentication/RBAC is enabled yet. Operational endpoints require access control before deployment.

Documentation: `docs/architecture/realtime-operations.md`.

## Phase H - Alert operations

Status: IMPLEMENTED / AUTHENTICATION-GATED FOR PRODUCTION.

Implemented: durable alert review transitions, acknowledgement/dismissal/escalation actions, review history, audit events, case timeline integration, API endpoints, and investigator UI controls.

Known limitations: actor identity is optional until authentication/RBAC, notifications are not implemented, and alert generation remains driven by existing realtime/risk workflows rather than a distributed alert queue.

Documentation: `docs/architecture/alert-operations.md`.

## Current phase

PHASE 6 — RISK INTELLIGENCE & INVESTIGATIVE SCORING

## Status

IMPLEMENTED for deterministic historical risk reassessment over persisted evidence; PostgreSQL runtime validation remains environment-dependent.

## Implemented

- Configurable risk-factor definitions and monotonic risk-band thresholds.
- Pure deterministic `RiskEngine` over trace, pattern, and source-backed attribution evidence.
- Evidence-required factors with duplicate pattern/entity deduplication and contribution caps.
- Risk bands: LOW, GUARDED, ELEVATED, HIGH, CRITICAL.
- Separate investigative priority and watch-status readiness.
- Immutable versioned assessments with risk delta and factor change tracking.
- PostgreSQL migration `006_risk_intelligence.sql` with assessment, factor, evidence, pattern, entity, transaction, alert-candidate, and audit-event records.
- Risk assessment/history/delta/factor/alert/trace/wallet APIs.
- Reviewable `RiskAlertCandidate` boundary; no automatic fraud alerting.
- Risk intelligence UI with posture, factor explanations, evidence counts, delta, and alert-candidate states.
- Audit event boundary for `RISK_ASSESSED`.

## Validation

- Backend: 44 passed, 2 skipped.
- Frontend: production TypeScript/Vite build passed.
- Frontend: 1 Vitest test passed.
- Python compilation and FastAPI import smoke passed.

## Known limitations

- PostgreSQL integration tests remain skipped when Docker/PostgreSQL is unavailable.
- Risk assessment is synchronous and operates on the selected bounded historical trace.
- No ML, sanctions dataset, or production authentication is implemented.
- Cross-chain risk consumes persisted cross-chain pattern observations only when a normal trace exists; full cross-chain risk subject modeling remains future work.
- Evidence ledger UI remains the existing capability surface; dedicated risk-to-ledger navigation is a future UI refinement.

## PHASE 7 — RRR REAL-TIME RETRACING

Status: IMPLEMENTED BOUNDARY / LIVE DEPENDS ON CONFIGURATION

Implemented: canonical realtime events, HMAC-validated Alchemy webhook intake, idempotent PostgreSQL event storage, case-scoped watch targets, reorg-safe observation handling, incremental transaction/transfer/evidence/graph application, timeline/change sets, reassessment hooks, and investigator monitoring workspace.

Known limitations: Alchemy webhook registration is provisioned outside this repository; WebSocket ingestion and confirmation-depth reconciliation are not enabled; automatic recursive watch expansion is not enabled; PostgreSQL runtime validation depends on an available database.

Next phase: PHASE 8 — CROSS-CHAIN INTELLIGENCE.

## PHASE 8 — CROSS-CHAIN INTELLIGENCE

Status: IMPLEMENTED BOUNDARY / PARTIAL RUNTIME

Implemented: Ethereum/Tron chain registry, chain-qualified graph identity, TronGrid historical provider boundary, bridge definition/detection contracts, correlation levels and provenance, cross-chain graph/trace limits, migration 008 persistence, cross-chain APIs, realtime integration hook, and investigator cross-chain workspace.

Known limitations: TronGrid requires `TRONGRID_API_KEY`; no Tron realtime adapter exists; no unverified bridge addresses are bundled; bridge definitions must be loaded from an approved source; cross-chain risk/pattern consumers are extension-ready but do not yet create Phase 5/6 records from cross-chain traces; Docker/PostgreSQL runtime validation depends on the local environment.

Next phase: PHASE 9 — INVESTIGATOR COPILOT.

## Evidence ledger integrity

Status: IMPLEMENTED / AUTHORIZATION-GATED FOR EXPORT

Implemented: canonical SHA-256 evidence hashes, deterministic evidence manifests, append-only chain-of-custody events, PostgreSQL migration `014_evidence_ledger.sql`, ledger/manifests/chain APIs, request correlation IDs, structured error envelopes, and investigator UI visibility for integrity status.

Known limitations: authenticated actor identity, signed exports, legal certification, and external evidence-vault integration are not enabled. Hashing proves consistency of the stored observation representation, not independent truth of an external provider payload.

Validation: backend `63 passed, 2 skipped` after this slice. PostgreSQL integration remains dependent on the local Docker/database runtime.

## Investigative reports

Status: IMPLEMENTED / AUTHENTICATION-GATED FOR OFFICIAL EXPORT

Implemented: persisted immutable report snapshots, evidence/pattern/risk/trace references, content hashing, report APIs, report-generation audit/timeline events, and investigator report preview UI. Reports explicitly distinguish observed facts from derived observations and include limitations.

Known limitations: actor identity is optional, reports are not signed legal filings, and authorized export, retention, and case-scoped RBAC remain future security controls.

## Cross-case intelligence

Status: IMPLEMENTED / EXACT-OVERLAP ONLY

Implemented: read-only case relationship query and investigator panel based on shared persisted wallet or transaction identities. No relationship is inferred from labels, timing, or address similarity.

Known limitations: relationship results are not yet persisted leads, confidence-reviewed collaboration workflows, or tenant-isolated intelligence. Authentication/RBAC remains required before sensitive deployment.

## Authentication boundary

Status: IMPLEMENTED BOUNDARY / DISABLED BY DEFAULT FOR LOCAL DEVELOPMENT

Implemented: backend-only RS256/ES256 JWT verification, explicit `DISABLED`/`NOT_CONFIGURED`/`READY` status, protected API middleware when enabled, request-safe error responses, and no inferred investigator identity.

Known limitations: no case-level authorization, role policy, JWKS discovery/rotation, revocation, SSO provisioning, or authenticated export. `AUTH_REQUIRED=true` must not be enabled without a trusted public key and issuer integration.

## Graph investigator workspace refinement

Status: IMPLEMENTED / DATA-DRIVEN UI

Implemented: investigator-grade dark command-center graph workspace with real SVG rendering from trace nodes and edges, asset filtering, zoom/fit/reset controls, keyboard-selectable observations, chain-aware node inspection and `chain:address` frontend identity keys, transaction/evidence detail inspection, risk-linked derived overlays, graph metrics, observed-flow analysis readout, trace limitations, and an explicit no-active-trace state. No fixture graph data is rendered by the production route.

Validation: frontend TypeScript/Vite build passed; frontend test passed; backend regression suite passed (`63 passed, 2 skipped`); Docker Compose syntax passed; localhost empty-state visual QA passed.

Known limitations: a populated graph interaction requires PostgreSQL-backed case/trace data; PostgreSQL runtime validation remains unavailable while the local Docker Linux engine is unavailable. The graph remains an analytical SVG projection of persisted observations and is not a chain-wide visualization.

Investigator workflow refinement: persisted cases in the case registry now expose an `OPEN CASE` action that reloads case context and the latest trace through the existing API. Cases with no trace show an explicit trace-unavailable state.

## Cross-chain correlation integrity hardening

Status: IMPLEMENTED / IDEMPOTENT CORRELATION IDs

Implemented: cross-chain correlation IDs and link UUIDs are deterministically derived from the source transaction, destination transaction, and bridge identity. Repeated bridge analysis now resolves to the same logical link and cannot create duplicate link relationships or orphan evidence references. Regression coverage verifies stable identities.

Correlation is fail-closed when a destination chain is missing: timing or symbol similarity cannot select an arbitrary network, and the result remains an unresolved inference until chain evidence is supplied.

Validation: backend suite `64 passed, 2 skipped`; Python compilation and diff validation passed.

## Wallet intelligence lookup

Status: IMPLEMENTED / PERSISTED OBSERVATIONS ONLY

Implemented: `GET /api/v1/wallets/{chain}/{address}` and a responsive Wallet Intelligence workspace using canonical wallet, graph-edge, transaction, case relationship, and evidence records. Ethereum addresses are normalized case-insensitively; Tron addresses preserve case-sensitive Base58 representation. The UI reports observed activity and explicitly avoids balance, ownership, or criminality claims.

Known limitations: the endpoint does not query a live chain provider or assert current balance; it returns 404 when the address has no persisted investigation record. Attribution and risk remain separate source-backed workspaces.

Integrity refinement: address normalization is now centralized and chain-specific. Ethereum identity is case-insensitive; Tron Base58 identity preserves case across wallet persistence, watch targets, chain-address records, cross-chain node IDs, and UI graph keys.

The same normalization is now applied during historical trace traversal, NetworkX graph construction, PostgreSQL graph-edge persistence, and Neo4j projection, preventing case loss between provider data and analytical/persistent representations.

## Phase 8A - Real backend connectivity and end-to-end investigation

Status: PARTIAL - connected workflow implemented; local PostgreSQL/provider runtime unavailable.

Implemented in this phase: audit matrix, authoritative dependency status endpoints (`/api/v1/system/status`, `/api/v1/system/providers`, `/api/v1/system/dependencies`), connected intake for case metadata/wallet/network/optional transaction reference, automatic persisted pattern and risk processing after trace, functional cross-workspace case tabs, dashboard metric navigation, and local simulated realtime watch/event controls.

Validation: backend `68 passed, 2 skipped`; frontend production build passed; frontend test passed; API smoke returned `UNAVAILABLE` for PostgreSQL with `InvalidPasswordError` and correctly exposed `NOT_CONFIGURED` for Alchemy, realtime, Neo4j, OFAC, and threat intelligence.

Remaining: run the database-backed end-to-end workflow with PostgreSQL, configure Alchemy for real historical/realtime data, validate Neo4j synchronization, add case-scoped authorization, complete wallet/transaction/evidence detail routes, and add full browser/database-state integration coverage. See `docs/audit/backend-connectivity-final.md`.

## Phase 8D - Operational proof and readable investigator surfaces

Status: PARTIAL - local development workflow proven

The Docker stack is now running with PostgreSQL, Neo4j, API and web services. `POST /api/v1/dev/seed-case` creates a clearly marked `DEVELOPMENT_FIXTURE` investigation through persisted case, wallet, transaction, graph, pattern, risk, watch, realtime, evidence and report stages. Database integrity reported zero orphan records during validation. The graph layout now follows observed hop relationships and uses semantic colors; the evidence workspace exposes provenance and readable record labels with loading, empty and retry states.

Live Alchemy remains `NOT_CONFIGURED` without `ALCHEMY_API_KEY`. Realtime development processing is `SIMULATED`, and alert creation is data-dependent on an actual risk delta. See `docs/audit/operational-readiness-final.md` and `docs/architecture/mobile-rrr.md`.
