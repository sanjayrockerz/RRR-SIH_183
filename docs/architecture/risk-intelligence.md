# Risk intelligence

Phase 6 calculates an explainable investigative risk posture from persisted Phase 3 graph evidence, Phase 4 source-backed attribution, and Phase 5 behavioral observations.

## Boundary

`TraceResult + PatternObservation[] + NearestEntityResult[] → RiskEngine → RiskAssessment → Risk Delta → Alert Candidate`

`RiskEngine` is a pure calculation boundary. It performs no provider calls, persistence, transaction signing, or external integration.

## Risk versus criminality

Risk bands (`LOW`, `GUARDED`, `ELEVATED`, `HIGH`, `CRITICAL`) describe investigative posture only. They are not legal classifications, proof of fraud, sanctions conclusions, or laundering determinations.

## Factors

The default configuration includes evidence-backed factors for rapid hop, fan-in/out, peel-chain-like flow, consolidation, burst activity, dormant activation, mixer/bridge/entity exposure, and graph hop depth. Definitions contain category, weight, cap, enablement, explanation template, and required evidence type. Missing evidence means the factor is not created.

Pattern and attribution duplicates are canonicalized before contribution calculation. Each factor contribution is capped by its definition and the final score is clamped to 0–100.

## Bands and priority

Default thresholds are configurable: `LOW < 20`, `GUARDED >= 20`, `ELEVATED >= 40`, `HIGH >= 60`, `CRITICAL >= 80`. Investigative priority is separate and considers the band plus recent observed activity. Live monitoring is never inferred from historical data.

## Versioning and delta

Every assessment is immutable and versioned per case/subject. A later assessment stores its predecessor, factor changes, score delta, calculation version, and the evidence state used. This provides the Phase 7 incremental reassessment boundary.

## Future boundary

Phase 7 can call `RiskEngine.assess` after each incremental graph/pattern update and compare the new immutable assessment with the previous one. Alert candidates are currently persisted as reviewable investigative signals; dispatch and notification remain future work.
