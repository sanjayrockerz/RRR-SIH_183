# ADR 0006: Explainable versioned risk posture

## Status

Accepted

## Decision

Risk intelligence is a deterministic, configurable weighted-contribution layer over persisted graph, pattern, attribution, and evidence records. Risk assessments are immutable and versioned by case and subject. Risk bands and investigative priority are separate fields.

## Rationale

Investigators need to see why a posture was calculated and how it changed when new evidence arrives. Versioning preserves historical decisions, while evidence joins make every factor auditable. Separating the risk engine from future real-time ingestion allows Phase 7 to reassess incrementally without changing the scoring contract.

## Constraints

No ML, unsupported criminality conclusions, legal classifications, or automatic enforcement actions are introduced. Factors without evidence are excluded, duplicate observations are deduplicated, and the score is bounded and reproducible.
