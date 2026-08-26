# Development status

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

- Backend: 30 passed, 2 skipped.
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
