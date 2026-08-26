# ADR 0008: Explicit chain identity and confidence-scored cross-chain links

## Decision

Represent an address as `(chain, address)` and represent bridge-mediated movement as an inferred `CROSS_CHAIN_LINK`, separate from observed transfer edges. Use provider capability states for Ethereum and Tron and persist raw normalized observations independently of correlations.

## Rationale

Address text is not a global identity, and a bridge deposit does not by itself establish the destination transaction or wallet. Separating observed facts from inferred links preserves forensic provenance and prevents weak timing or symbol matches from becoming facts.

## Consequences

Tron can be added without changing graph semantics, but remains unavailable until a configured provider is present. Bridge detection is intentionally limited until curated definitions are source validated. Cross-chain results can be partial or unresolved.
