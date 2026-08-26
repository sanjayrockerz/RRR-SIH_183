# Bridge Intelligence

`BridgeRegistry` is data-driven. `BridgeDefinition` contains chain-specific deposit, withdrawal, router, token mapping, event signature, source, and version metadata. `BridgeDetectionEngine` only recognizes an interaction when an observed transfer touches a contract in a source-backed definition. Contract names and token symbols alone do not identify a bridge.

The repository does not bundle unverified bridge addresses. Operators must load curated definitions from an approved source before production bridge detection is enabled.
