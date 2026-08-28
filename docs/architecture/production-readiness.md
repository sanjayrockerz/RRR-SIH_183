# Production readiness assessment

## Current verdict

**Status: NOT PRODUCTION READY for sensitive LEA deployment.**

**Status: READY FOR CONTROLLED ENGINEERING/DEMO USE** when using configured providers, non-sensitive fixtures, and the explicit historical/simulated boundaries.

## Readiness gates

| Gate | State | Evidence |
|---|---|---|
| Deterministic domain and API contracts | PASS | Pydantic models, versioned routes, provider abstractions |
| Persistent source of truth | PARTIAL | PostgreSQL repository and migrations exist; local runtime credentials are unresolved |
| Provider provenance | PARTIAL | Raw references and provider fields exist for blockchain observations; enrichment provenance not implemented |
| Idempotency | PASS for implemented paths | Transaction, trace, pattern, realtime and cross-chain uniqueness boundaries exist |
| Historical trace safety | PASS within configured bounds | Bounded hops/nodes/edges/transactions/duration |
| Realtime authenticity | PARTIAL | HMAC/signature and replay boundaries exist; deployment/webhook operations are not validated here |
| Reorg handling | PARTIAL | Event model/application handles removed/reorged observations; confirmation-depth operations remain limited |
| Authentication | PARTIAL | Opt-in RS256/ES256 bearer-token verification exists; OIDC/JWKS deployment and identity lifecycle are not configured |
| Authorization / case isolation | FAIL | Routes do not enforce actor or case permissions |
| Secrets management | PARTIAL | Environment configuration; no secret in frontend; production secret manager absent |
| Evidence integrity | PARTIAL | Canonical content hashes, deterministic manifests, and custody events exist; authenticated export/legal certification are not enabled |
| Auditability | PARTIAL | Audit/timeline persistence exists; actor/request/before-after coverage incomplete |
| Threat intelligence | FAIL | No connected threat provider or source ingestion |
| Sanctions | FAIL | OFAC data not ingested/screened |
| Reporting/export | FAIL | Report service and authorization are not implemented |
| Observability | PARTIAL | Logs and health endpoints exist; metrics/traces/alerting are absent |
| Scale | MVP only | PostgreSQL + NetworkX bounded analysis; no measured high-volume benchmark |

## Required production controls

Before handling real complaint PII or sensitive investigations:

1. OIDC/SSO with short-lived tokens, trusted issuer/JWKS validation, and role claims. The current JWT boundary must be enabled and integrated with the deployment identity provider.
2. Case-scoped authorization on every read/write/export route.
3. TLS, reverse proxy, request IDs, rate limiting, body limits, and secure headers. RRR now emits a validated `X-Request-ID` and compatible structured error envelope; deployment controls remain required.
4. Secret manager integration for provider/database credentials.
5. Authenticated immutable evidence-manifest export with content hashes and export audit records.
6. Database backups, restore drills, migration rollback policy, and retention policy.
7. Structured logs and metrics with provider latency/error/rate-limit visibility.
8. Webhook replay, deduplication, dead-letter, retry, and reorg runbooks.
9. Threat/sanctions source versioning and review workflows.
10. Security review, dependency scanning, DAST/API testing, and an incident response plan.

## Security language rule

The system may produce observed facts, source-backed attribution, behavioral observations, and explainable investigative posture. It must not convert any of those into a legal conclusion or unsupported label.
