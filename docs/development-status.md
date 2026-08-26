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

- Backend: 19 passed, 2 skipped.
- Frontend: production TypeScript/Vite build passed.
- Frontend: 1 Vitest test passed.
- Python compilation and FastAPI import smoke passed.

## Known limitations

- PostgreSQL integration tests remain skipped when Docker/PostgreSQL is unavailable.
- Risk assessment is synchronous and operates on the selected bounded historical trace.
- No real-time monitoring, ML, sanctions dataset, cross-chain scoring, or production authentication is implemented.
- Watch status is a readiness field; monitoring lifecycle actions are future Phase 7 work.
- Evidence ledger UI remains the existing capability surface; dedicated risk-to-ledger navigation is a future UI refinement.

## Next phase

PHASE 7 — RRR REAL-TIME RETRACING
