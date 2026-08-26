# Pattern intelligence

Phase 5 converts bounded, observed graph behavior into explainable `PatternObservation` records. It does not produce a risk score, a probability of criminality, or a laundering classification.

## Architecture

`TraceResult → PatternService → PatternEngine → modular detectors → PatternObservation → PostgreSQL`

The engine consumes only the selected trace and optional Phase 4 `NearestEntityResult` attribution. It never scans the blockchain independently and never changes the graph engine.

## Detector interface

Each detector implements `PatternDetector.detect(trace, config, attributions)` and returns zero or more observations. `PatternEngine` owns detector composition and applies deterministic fingerprints based on case, trace, pattern type, affected nodes, and transaction hashes.

Implemented detectors:

- `RAPID_HOP`: connected transfers whose inter-hop timestamps meet the configured threshold.
- `FAN_OUT`: one source distributing to the configured number of distinct destinations within a time window.
- `FAN_IN`: multiple sources transferring to one destination within a time window.
- `PEEL_CHAIN`: repeated forwarding of most of the prior amount with a configured residual ratio.
- `CONSOLIDATION`: fan-in observation explicitly described as consolidation.
- `BURST_ACTIVITY`: high transaction density in the available trace window; no statistical baseline claim.
- `DORMANT_ACTIVATION`: a long observed gap followed by a burst, explicitly limited to available observations.
- `MIXER_INTERACTION`: observed contact with a Phase 4 mixer-attributed address/contract.
- `BRIDGE_INTERACTION`: observed contact with a Phase 4 bridge-attributed address/contract; continuation is unresolved.
- `ENTITY_EXPOSURE`: a traced path reaches a source-backed attributed entity.

## Configuration

`PatternDetectionConfig` keeps minimum hops, inter-hop seconds, fan thresholds, retention ratios, burst windows, and dormancy windows outside detector logic. Analysis uses defaults unless an explicit configuration is submitted with the analyze request.

## Evidence and language

Every observation retains transaction hashes, graph edge IDs, evidence IDs, affected nodes, timestamps, and detector metadata. Descriptions use `Observed`, `Potential`, and `Source-backed` language. An observation is not a finding of fraud, laundering, or criminal conduct.

## Persistence and APIs

Migration `005_fraud_patterns.sql` creates typed query fields in `pattern_observations`, JSONB detector metadata, a unique fingerprint, and a normalized pattern-to-evidence join table.

- `POST /api/v1/cases/{case_id}/patterns/analyze`
- `GET /api/v1/cases/{case_id}/patterns`
- `GET /api/v1/cases/{case_id}/patterns/{pattern_id}`
- `GET /api/v1/cases/{case_id}/patterns/summary`
- `GET /api/v1/traces/{trace_id}/patterns`

Analysis is explicit and synchronous for the MVP. Repeated analysis of the same trace deduplicates through the fingerprint uniqueness constraint.

## Complexity and limitations

The engine operates on bounded trace edges. Fan and burst detectors sort or group the in-memory trace edges; path-based detectors operate on persisted trace paths. No provider-wide historical baseline exists, so burst and dormancy observations are descriptive and limited to the observation window.

## Risk boundary

`PatternObservation` is the input boundary for the future `RiskEngine`. Phase 5 does not implement risk scoring, alert dispatch, ML, or automatic enforcement actions.
