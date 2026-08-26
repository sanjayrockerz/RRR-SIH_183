# Investigative scoring methodology

RRR-Realtime uses a transparent weighted contribution model rather than ML or an unexplained fraud score.

`raw_score = Σ factor contributions`

`normalized_score = clamp(raw_score, 0, 100)`

Each factor contribution is `min(default_weight × unique qualifying observations, max_contribution)`. Only observations with transaction, graph-edge, pattern, or attribution evidence references qualify. Duplicate pattern fingerprints and duplicate entity/address observations do not double count.

The result includes the score, band, priority, factor definitions, explanations, confidence levels, transaction hashes, pattern IDs, entity IDs, evidence IDs, calculation version, and timestamps. Two calculations over the same evidence and configuration produce the same score and factor contributions.

The score is an investigative prioritization aid. It does not establish ownership, intent, fraud, laundering, criminality, or legal liability.
