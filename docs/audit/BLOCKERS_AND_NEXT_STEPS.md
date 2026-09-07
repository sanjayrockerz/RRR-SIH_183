# Blockers and Next Steps

## Blocking production readiness

| Priority | Finding | Evidence | Required action |
|---|---|---|---|
| P0 | Authentication and authorization are disabled | `.env`: `AUTH_REQUIRED=false`; no RBAC policy in source | Integrate OIDC/SSO, enforce JWT validation, case-level authorization and role policy before sensitive data |
| P0 | Database integrity is not clean | `/api/v1/system/integrity`: 17 transactions without case links; 63 risk factors without evidence links | Identify and repair orphan records with a migration/reconciliation job; add CI integrity gate |
| P0 | Secrets/documentation risk | Environment is secret-bearing; deployment documentation contains a credential-like Alchemy value | Rotate any exposed credential, remove secrets from docs/history, use secret manager and scanning |
| P1 | Neo4j unavailable | `/api/v1/graph/status`: `UNAVAILABLE` | Start/configure Neo4j, verify migrations/credentials, or document PostgreSQL-only fallback and test it |
| P1 | Realtime webhook not configured | `/api/v1/realtime/health`: `NOT_CONFIGURED` | Register provider webhook, configure signing key/ID, test retries, confirmations, reorg/removal and dead-letter behavior |
| P1 | TronGrid not configured | System status `trongrid: NOT_CONFIGURED` | Configure a valid provider key and run Ethereum-to-Tron integration tests |
| P1 | Sanctions/threat sources absent | OFAC and threat intelligence `NOT_CONFIGURED`; sanctions count 0 | Load versioned approved datasets, preserve checksums/retrieval times and define match semantics |
| P1 | Cross-chain correlation depends on explicit observations | `CrossChainService` fail-closes when destination chain/evidence is absent | Integrate supported bridge/event sources and test exact/strong/probable/unresolved outcomes on real fixtures |
| P2 | Global realtime watch matching can cross-associate identical addresses | `RealtimeService._all_watches` scans all active watches by address/chain | Scope event routing to case/watch ownership and add multi-case isolation tests |
| P2 | Risk calibration and evidence completeness | Rule engine is deterministic but current synthetic scores are data-dependent; integrity shows orphan factor links | Define reviewed scoring policy, factor traceability requirements and calibration/acceptance datasets |
| P2 | Report completeness varies with upstream data | `ReportService` emits explicit no-data sections | Add report completeness checklist and fail/warn when required evidence sections are missing |
| P2 | Frontend test coverage is minimal | One frontend test file/test passed | Add page/API contract, error, refresh, case-isolation and graph invariant tests |

## Demonstration blockers

- Use `DEVELOPMENT_FIXTURE` or the hardcoded-case endpoint only when demonstrating synthetic behavior.
- Do not describe synthetic realtime events as live blockchain events.
- Do not describe the Demo Exchange registry as real-world attribution.
- Do not claim SAHYOG/NCRP connectivity.
- Do not claim Neo4j operation until the status endpoint is `SUPPORTED`.
- Do not present an empty sanctions status as a clean sanctions result.
- Do not use the current integrity `WARN` snapshot as a forensic-quality guarantee.

## Recommended implementation order

1. Rotate/remove credentials and add repository secret scanning.
2. Repair database orphan relationships and add a fail-closed integrity gate.
3. Enforce authentication/RBAC and actor identity on all case/action/evidence routes.
4. Make realtime event-to-case routing explicit and test identical addresses across cases.
5. Bring up Neo4j and verify projection/rebuild/consistency behavior.
6. Configure and test TronGrid, bridge definitions, source/destination events and asset mappings.
7. Load approved sanctions/threat datasets with source version/checksum/provenance.
8. Expand report content/QA and ensure every displayed claim has a persisted reference.
9. Add frontend end-to-end tests and API schema contract tests.
10. Build a separate mobile client against the existing API; keep intelligence server-side.

## Acceptance gates before production

- `/health`, dependencies and integrity are green or explicitly approved exceptions.
- Authentication is required and unauthorized case access is rejected.
- PostgreSQL migrations run from a clean database and integrity has zero unapproved orphans.
- Neo4j projection status and rebuild are tested, or PostgreSQL-only mode is formally documented.
- Live provider credentials are stored outside source control and provider failure behavior is tested.
- Realtime webhook signature, deduplication, confirmations, removed events, retries and DLQ are tested.
- Cross-chain links show source TX, destination TX, bridge, asset/amount, confidence and evidence; unknown links remain unknown.
- VASP/entity labels come only from versioned source-backed records.
- Reports contain actual case values and pass PDF visual/content QA.
- Threat/sanctions feeds have versioned provenance and an operational update owner.
- Mobile security, secure storage, offline semantics and device controls are specified before release.
