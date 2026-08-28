# Phase 8A backend connectivity matrix

Audit date: 2026-08-27

This matrix records the repository state before the Phase 8A implementation changes. `CONNECTED` means the UI calls a backend route and the route reaches a persistence/provider boundary; it does not mean the local dependency is currently available. `PARTIAL` means only part of the intended workflow is connected. `SIMULATED` and `NOT_CONFIGURED` are explicit capability states, not successful live integrations.

## Surface matrix

| UI surface | Frontend API/call | FastAPI endpoint | Persistence/table | Real provider dependency | Current state |
|---|---|---|---|---|---|
| Dashboard | `dashboardSummary()`, `systemStatus()` | `GET /api/v1/dashboard/summary`, `GET /api/v1/system/status` | Repository aggregates over cases, wallets, transactions, alerts, watches, entities and timeline | PostgreSQL; provider status is separate | PARTIAL: no hardcoded metrics in the active dashboard, but no central dependency breakdown and local PostgreSQL is unavailable |
| Cases | `listCases()`, `getCase()` | `GET /api/v1/cases`, `GET /api/v1/cases/{id}`, lifecycle routes | `cases`, case-wallet/case-transaction relations | None for registry reads | CONNECTED: case index is PostgreSQL-backed; direct case opening preserves latest trace when present |
| Investigations/intake | `createCase()`, `addWallet()`, `trace()` | `POST /api/v1/cases`, `POST /api/v1/cases/{id}/wallets`, `POST /api/v1/cases/{id}/traces` | `cases`, `wallets`, `transactions`, `transaction_transfers`, `trace_runs`, graph/evidence tables | Alchemy for Ethereum; Tron provider for Tron | PARTIAL: actual chained API flow exists, but the UI only submits Ethereum wallet data and does not submit complaint reference, victim notes, optional transaction hash, or selected source |
| Wallet intelligence | `walletIntelligence()` | `GET /api/v1/wallets/{chain}/{address}` | Wallet, transaction, case and evidence relations | No live lookup; persisted observations only | CONNECTED / HISTORICAL: no balance or ownership claim; no wallet collection/transaction subroutes |
| Transaction graph | `GraphInspector`; case graph routes | `GET /api/v1/cases/{id}/graph`, graph paths/metrics | `trace_runs`, `graph_nodes`, `graph_edges`, evidence relations | Alchemy only upstream; NetworkX analytical engine; optional Neo4j projection | CONNECTED / PARTIAL: UI renders persisted trace nodes/edges; richer graph filters, entity/risk/pattern links and direct transaction navigation are incomplete |
| Entities/VASPs | `listEntities()` | `GET /api/v1/entities`, attribution routes | `entities`, `attribution_sources`, `address_attributions`, provenance tables | Curated catalog only; no commercial provider enabled | CONNECTED / NOT_CONFIGURED for enrichment: catalog is real persisted data when present, but screen is not case-scoped and has no full detail navigation |
| Patterns | `analyzePatterns()`, `patterns()`, `patternSummary()` | Case pattern analyze/list/summary/detail routes | `pattern_observations`, pattern evidence/transaction references | No external provider; deterministic engine | CONNECTED: explicit analyze action persists/reads observations; no direct graph-region navigation yet |
| Risk | `assessRisk()`, risk/history/delta/factors/alerts | Case risk assessment/history/delta/factors/alerts routes | `risk_assessments`, `risk_factors`, `risk_alert_candidates`, audit events | No external provider; deterministic engine | CONNECTED: React does not calculate risk; factor-to-evidence navigation is incomplete |
| Realtime | watches, timeline, changes, alerts, capabilities; simulated event route exists | Case watch routes, Alchemy webhook, simulated event, replay/failure routes | `watch_targets`, `realtime_events`, applications, attempts, timeline, changes, alerts | Alchemy webhook credentials for live mode; explicit simulated mode | PARTIAL: durable processing loop exists; live watch is credential-gated; simulated watch/event path is available in code but database runtime is not currently verifiable |
| Alerts | `listAlerts()`, `reviewAlert()` | `GET /api/v1/alerts`, case review/history routes | `alerts`, `alert_reviews`, audit/timeline | Produced by risk/realtime workflows | CONNECTED: list and review actions are persisted; alert detail deep-linking is incomplete |
| Evidence | `listEvidence()`, ledger and manifest calls | Case evidence, ledger, manifest and custody routes | `evidence`, `evidence_manifests`, manifest items, custody events | Upstream provider provenance; no vault | CONNECTED / PARTIAL: case evidence and integrity manifest are persisted; global evidence/detail/export routes are missing |
| Reports | `listReports()`, `createReport()` | Case report list/create/detail routes | `investigation_reports` | None; report derives persisted case state | CONNECTED: immutable snapshot/preview exists; authenticated export/signing is not implemented |
| Cross-chain | chains, summary, links, analyze | Chain capability and case cross-chain routes | Chain registry, bridge/correlation, cross-chain trace/pattern tables | TronGrid credentials and approved bridge registry | PARTIAL: Ethereum/Tron boundary and persistence exist; live Tron and approved bridge data are not configured |

## Cross-cutting findings

1. The active frontend uses a centralized `src/api.ts` request helper, but the client is incomplete: there are no typed global transaction/evidence/wallet collection clients, no retry helper, and error parsing only reads `detail`.
2. `GET /api/v1/system/status` exists, but `/api/v1/system/providers` and `/api/v1/system/dependencies` do not. Existing `/api/v1/providers`, `/api/v1/provider/capabilities`, `/api/v1/realtime/health`, `/api/v1/graph/status`, and `/api/v1/auth/status` expose fragmented health state.
3. PostgreSQL is the declared source of truth and there is no intentional in-memory fallback. The local API smoke check reports `UNAVAILABLE` with `InvalidPasswordError`; Docker cannot currently connect to the Docker Desktop Linux engine.
4. The active dashboard metrics are backend-derived. The older `Dashboard` component in `pages.tsx` contains unused hardcoded display values and must be removed or explicitly marked demo-only.
5. The intake UI presents fields that are not yet part of the submitted request. This can make the screen appear more complete than the persisted case model.
6. Authentication verification is present as an opt-in boundary, but case-level authorization and tenant isolation are not enforced.
7. Neo4j projection/query boundaries exist, but PostgreSQL remains authoritative and Neo4j has not been runtime-validated in this environment.

## Required implementation order from this audit

1. Fix and expose one authoritative dependency-health response.
2. Make PostgreSQL diagnostics and migration/runtime failures actionable.
3. Complete the intake request contract and verify the case → wallet → trace → persisted graph/evidence path.
4. Connect case context to every workspace and add missing detail/deep-link routes.
5. Exercise simulated realtime against PostgreSQL, then separately validate Alchemy HMAC/live mode.
6. Add database-state integration coverage and update the final connectivity audit with observed results.
