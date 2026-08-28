# RRR implementation roadmap

This roadmap follows controlled vertical slices. Each phase requires inspect → implement → test → build → API smoke test → documentation update before the next phase.

## Phase A — System audit (current)

- [x] Repository and dependency audit.
- [x] Capability maturity matrix.
- [x] Production-readiness gates.
- [x] Target runtime architecture.
- [x] Provider and cybersecurity boundaries documented.

## Phase B — Backend connection cleanup

- Complete case lifecycle and assignment contracts.
- Replace hardcoded dashboard metrics with aggregate APIs.
- Finish evidence, entity, alerts, timeline, and report route connectivity.
- Add API request IDs and consistent error envelopes.
- Add contract tests for every UI-used endpoint.

## Phase C — Graph projection

- [x] Add optional Neo4j service only as a rebuildable projection.
- [x] Create deterministic node/relationship IDs and idempotent projection.
- [x] Add health/capability state and bounded neighbor/shortest-path APIs.
- [x] Keep PostgreSQL and NetworkX behavior intact.
- [ ] Add realtime incremental projection and rebuild/checkpoint tooling.

## Phase D — Provider operations

- Add provider registry/router and health records.
- Implement explicit Alchemy/Etherscan capability comparison.
- Add timeout, rate-limit, retry, circuit-breaker, and raw-payload retention policies.
- Validate provider credentials without exposing secrets.

## Phase E — Entity/VASP intelligence

- Version curated attribution imports.
- Add entity-address provenance and conflict review.
- Add commercial `EntityIntelligenceProvider` adapter boundary; no fake vendor results.

## Phase F — Cyber intelligence and sanctions

- Add threat indicator, sanctions screening, and contract-security domain models.
- Ingest versioned OFAC data with direct/indirect/unknown outcomes.
- Add curated scam reports and optional Chainabuse/commercial adapters.
- Keep wallet risk and contract risk separate.

## Phase G — Realtime hardening

- Add webhook delivery ledger, retries, dead-letter state, and operational replay tools.
- Add confirmation-depth and reorg reconciliation policy.
- Add live UI stream only after runtime provider configuration is verified.

## Phase H — Alert operations

- Complete alert review, acknowledgement, escalation, and notification paths.
- Link every alert to transaction, edge, pattern, risk factor, and evidence.

## Phase I — Evidence ledger

- Evidence vault, immutable manifests, content hashes, export authorization, and chain-of-custody events.

## Phase J — Timeline

- Complete event taxonomy, chronological reconstruction, investigator notes, and audit correlation.

## Phase K — Cross-chain

- Credentialed Tron data path, approved bridge registry, correlation tests, cross-chain graph projection, and confidence-reviewed watch expansion.

## Phase L — Reports

- Evidence-backed report templates separating FACT, OBSERVATION, INFERENCE, and INVESTIGATIVE LEAD.

## Phase M — Investigator command center

- Replace hardcoded metrics with real aggregate APIs and distinct workspaces for wallet, transaction, threat, risk, realtime, evidence, and reports.

## Phase N — Authentication/RBAC

- OIDC/SSO, role policy, case isolation, export authorization, audit actor identity, and secure deployment controls.

## Phase O — End-to-end validation

- Postgres/Neo4j integration environment, provider-backed smoke flow, realtime replay flow, security testing, load tests, backup/restore drill, and documented live/not-configured/simulated capability report.
