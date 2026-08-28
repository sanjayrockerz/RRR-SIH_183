# Sanctions and threat intelligence

The backend has provider-independent persisted source, indicator, sanctions and contract-security boundaries. Screening currently supports exact chain-aware address matching over explicitly persisted records. `DIRECT_MATCH`, `NO_MATCH`, `UNKNOWN` and `NOT_CONFIGURED` remain distinct outcomes; no indirect exposure is inferred as a legal violation.

Live OFAC or commercial threat feeds are not bundled. Dataset version, source, retrieval time and evidence references are required before a feed is treated as configured.
