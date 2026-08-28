# Cybersecurity intelligence architecture

RRR separates blockchain facts from external intelligence. A provider may report a transfer, an intelligence source may associate an address with a threat category, and the risk engine may use both as evidence-backed inputs. None of these layers alone establishes criminality.

## Planned provider contracts

```text
BlockchainProvider
RealtimeProvider
EntityIntelligenceProvider
ThreatIntelligenceProvider
SanctionsProvider
ContractSecurityProvider
PriceProvider
```

All contracts should return capability state, normalized records, provenance, and raw references. The domain layer must not depend on a vendor name.

## Threat indicators

Future `ThreatIndicator` records should include category, source, confidence, observed time, expiration, provider, evidence IDs, and scope. Categories may include scam report, phishing, ransomware, exploit, malicious contract, mixer exposure, or compromised infrastructure only when the source supports the category.

## Sanctions

Screening must distinguish `DIRECT_MATCH`, `INDIRECT_EXPOSURE`, `NO_MATCH`, and `UNKNOWN`. A direct list result is a source-backed screening result. Indirect exposure must retain the path, distance, amount/time context, source, and method. The UI must not collapse any of these into a generic “sanctioned wallet” label.

## Contract and token security

Wallet investigative posture and smart-contract/token security are separate dimensions. A contract finding may include verified status, proxy status, creator, exploit indicators, token metadata, and provider provenance. It must not silently increase wallet risk without an explicit, evidence-linked risk-factor definition.

## Security controls

Before production LEA deployment, RRR requires OIDC/SSO, RBAC, case-level authorization, export authorization, rate limiting, TLS termination, secret management, immutable audit events, webhook replay protection, and evidence export policy. The API now adds validated request IDs and a backward-compatible structured error envelope. Evidence manifest hashing and custody events exist, but production identity, authorization, and authorized export remain disabled.
