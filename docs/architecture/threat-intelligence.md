# Cyber-intelligence foundation

Phase F introduces a provider-independent `CyberIntelligenceProvider` boundary. Approved datasets or commercial adapters can implement address screening without coupling case services to a vendor. The current implementation is `CuratedSanctionsProvider`, which accepts persisted, versioned records.

Threat indicators, sanctions records, and contract-security findings are separate concepts. A blockchain observation is not itself a threat indicator, and an investigative risk posture is not a sanctions determination.

All provider data is untrusted input. Adapters must normalize values, preserve source references and dataset versions, and attach evidence identifiers where available. No provider secret is returned to the frontend.

## Current capability states

If no approved sanctions records are persisted, screening returns `NOT_CONFIGURED`, not `NO_MATCH`. A configured source with no exact record returns `NO_MATCH`; an exact chain-aware address match returns `DIRECT_MATCH` and requires investigator review. Indirect matching is intentionally not implemented because timing, symbol similarity, and address resemblance are insufficient evidence.

## Future extension

Commercial threat-intelligence, sanctions, scam-report, and contract-security adapters may be added behind the same interface. They must expose source, version, retrieval time, confidence, and evidence provenance. Their results must remain distinct from canonical on-chain facts.
