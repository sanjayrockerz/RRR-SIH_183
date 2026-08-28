# RRR current-state cybersecurity audit

Updated: 2026-08-26

## Executive conclusion

RRR is a credible evidence-first blockchain investigation foundation, not yet a production LEA system. Its strongest implemented path is bounded historical Ethereum tracing through Alchemy, persisted into PostgreSQL and analyzed by graph, pattern, attribution, and deterministic risk services. Realtime and cross-chain capabilities have explicit boundaries, but depend on configuration and approved data sources. Authentication, authorization, reports, case collaboration, and production export controls are not implemented; cyber-intelligence screening and evidence-integrity manifests now have explicit source/configuration boundaries.

The most important integrity rule is currently respected: observed blockchain facts, source-backed attribution, derived patterns, and investigative risk posture remain separate. The product must continue to expose capability state rather than convert missing provider data into a positive conclusion.

## End-to-end dependency map

```text
React investigator UI
  -> FastAPI routes
  -> application services (trace, pattern, risk, realtime, cross-chain)
  -> PostgresCaseRepository / persistence mixins
  -> PostgreSQL migrations and evidence relationships
  -> provider adapters (Alchemy Ethereum, TronGrid boundary)
```

The persistence repository is the source of truth. NetworkX is rebuilt for bounded analysis and is not the authority for historical facts.

## Maturity matrix

| Capability | UI | API | Service | DB | External data | Tests | Maturity |
|---|---|---|---|---|---|---|---|
| Case create/read | Connected | Implemented | Repository-backed | Yes | None | Unit + opt-in integration | Real / runtime DB blocked |
| Case list/lifecycle | Connected for list | Implemented | Repository-backed | Yes | None | Import/build only | Real / newly integrated |
| Wallet intake | Connected | Implemented | Validation + deduplication | Yes | None | Covered | Real |
| Historical Ethereum transfers | Connected | Implemented | TraceService + Alchemy | Yes | Alchemy | Mocked provider tests | Real / credential required |
| Token transfers/receipts/blocks | Partial | Boundary/implemented where adapter supports | Data fabric | Yes | Alchemy | Mocked | Partial |
| Graph/path/fund flow | Connected | Implemented | NetworkX bounded graph | Reconstructable | Normalized observations | Covered | Real / bounded |
| Entity/VASP attribution | Partial | Implemented | Curated attribution engine | Yes | Curated dataset | Covered | Real / source-limited |
| Behavioral patterns | Connected | Implemented | Modular detectors | Yes | Trace observations | Covered | Real |
| Risk posture/delta | Connected | Implemented | Deterministic rule engine | Yes | Patterns/attributions | Covered | Real / not legal risk |
| Realtime monitoring | Connected but gated | Implemented boundary | Signed webhook + event pipeline | Yes | Alchemy webhook | Unit tests | Partial / not configured |
| Cross-chain tracing | Connected but gated | Implemented boundary | Chain/bridge/correlation contracts | Yes | TronGrid/curated bridges | Unit tests | Partial / not configured |
| Sanctions screening | Not connected | Not implemented | None | No | OFAC not ingested | None | Architecture-only |
| Scam/threat intelligence | Not connected | Not implemented | None | No | No provider | None | Architecture-only |
| Contract/token security | Not connected | Not implemented | None | No | No GoPlus adapter | None | Architecture-only |
| Cross-case linking | Not connected | Not implemented | None | Partial reusable entities | None | None | Not implemented |
| Reports/export | Connected report preview | Implemented snapshot service | Yes | Persisted reports with evidence/pattern/risk references | Canonical evidence ledger | Unit/API/build coverage | Implemented / export authorization pending |
| Authentication/authorization | No login enforcement by default | Opt-in JWT boundary | Token verification only | No actor/case enforcement | External OIDC/JWT issuer required | Unit coverage | Partial / production blocked until enabled and authorized |
| Audit events | No actor identity | Partial | Persistence boundary | Yes | None | Partial | Partial |
| System health | Partial | `/health`, `/api/v1/system/status` | Repository readiness | N/A | Provider capability endpoints | Smoke tested | Real / honest degraded state |

## Security findings and priorities

### P0 — required before sensitive deployment

- Add OIDC/SSO authentication and case-scoped authorization. Do not infer investigator identity from the current UI initials.
- Add tenant/case access checks to every read, mutation, evidence export, and webhook-associated operation.
- Put the API behind TLS, a trusted reverse proxy, request-size limits, rate limits, structured request IDs, and secret-managed deployment configuration.
- Keep PostgreSQL unavailable as a hard failure for data operations; never restore an in-memory fallback.
- Add authenticated evidence export manifests with content hashes and actor/action audit events. The current ledger supports hashing/manifests/custody review but not authorized export.

### P1 — strongest blockchain-cybersecurity value

- Introduce provider-independent `ThreatIntelligenceProvider`, `SanctionsProvider`, and `ContractSecurityProvider` contracts.
- Persist provider provenance, retrieval time, source version, raw reference, confidence, and expiration for every external intelligence result.
- Add OFAC dataset ingestion as a versioned screening source. A match must be reported as a source result, not as a criminal determination.
- Add contract/token security findings as a separate dimension from wallet investigative risk.
- Add provider health and latency telemetry to system operations.

### P2 — scale and investigator differentiation

- Case-linking engine over shared wallets, transactions, entities, and evidence with confidence-scored leads.
- Temporal analytics and evidence-backed report generation.
- Queue-backed asynchronous processing after measured workload requires it; do not add Redis/Kafka solely for appearance.

## Current claim boundary

RRR can currently say: “The configured provider returned this normalized blockchain observation, which was persisted and used to derive this bounded graph/pattern/risk result.”

RRR cannot currently say: “This address is sanctioned,” “this address is criminal,” “this exchange owns the wallet,” or “this cross-chain continuation is live” without an appropriate source-backed capability being configured and persisted.
