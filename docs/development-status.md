# Development status

## Current phase

PHASE 5 — FRAUD PATTERN INTELLIGENCE

## Status

IMPLEMENTED for bounded historical trace observations; PostgreSQL runtime validation remains environment-dependent.

## Implemented

- Configurable `PatternDetectionConfig`.
- Modular `PatternEngine` and `PatternDetector` boundary.
- Rapid-hop, fan-in, fan-out, peel-chain, consolidation, burst-activity, dormant-activation, mixer-interaction, bridge-interaction, and entity-exposure detectors.
- Evidence-backed `PatternObservation` model with explicit status, confidence level, severity, explanations, affected graph facts, and evidence IDs.
- Deterministic fingerprints and PostgreSQL deduplication.
- Migration `005_fraud_patterns.sql` with normalized pattern/evidence links.
- Explicit analyze/list/detail/summary APIs.
- Investigator Patterns workspace with explicit analysis action and evidence-backed detail panel.
- No risk score, ML, criminality claim, automatic alert dispatch, or real-time processing.

## Validation

- Backend: 15 passed, 2 skipped.
- Frontend: production TypeScript/Vite build passed.
- Frontend: 1 Vitest test passed.
- Python compilation passed.

## Known limitations

- PostgreSQL integration tests remain skipped when Docker/PostgreSQL is unavailable.
- Pattern analysis is synchronous and operates only on the selected bounded trace.
- Burst and dormancy detectors have no wallet-wide statistical baseline; they report only available observation-window facts.
- Pattern-to-graph visual highlighting and investigator notes are prepared UI boundaries but not yet persisted as separate workflow features.
- RiskEngine and alert dispatch remain future capabilities.

## Next phase

PHASE 6 — RISK INTELLIGENCE & INVESTIGATIVE SCORING
