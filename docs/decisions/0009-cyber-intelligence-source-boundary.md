# ADR 0009: Source-backed cyber-intelligence boundary

## Decision

Keep threat indicators, sanctions records, and contract-security findings separate from canonical blockchain observations and investigative risk assessments. Access them through provider-independent interfaces and persist source/version/retrieval provenance.

## Rationale

Blockchain facts, external intelligence, and investigative interpretation have different evidentiary status and update lifecycles. Combining them into one label would make a provider result look like an on-chain fact and would make later reassessment non-reproducible.

## Consequences

The current exact-match sanctions provider returns explicit `NOT_CONFIGURED`, `NO_MATCH`, and `DIRECT_MATCH` states. Commercial and government sources can be added later without changing case or graph services. Indirect matching and automatic legal conclusions remain intentionally out of scope.
