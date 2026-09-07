# Implementation Status Matrix

Evidence is based on source inspection plus local checks on 2026-08-28. `REAL DATA` means the path can consume provider/database data; it does not mean credentials or external datasets are present in every environment.

| Feature | Frontend | API | Service | Database | Real data | Status | Evidence |
|---|---|---|---|---|---|---|---|
| Cases | Case list/intake/workspace | CRUD/open/status routes | Repository | `cases`, workflow | Yes | PASS | `App.tsx`, `main.py`, `persistence.py` |
| Open Case | Case context restore | `GET /cases/{id}` + summary/graph | `openCase` workflow | Case-scoped joins | Yes | PASS | `App.openCase`, routes 798-810 |
| Overview | Command center | summary/operational state | state aggregation | workflow/risk/timeline | Yes | PASS | `CaseCommandCenter.tsx`, `main.py` |
| Transaction ledger | `TransactionLedger` | `/transactions` | repository query | transactions/transfers/case links | Yes/fixture | PASS | component, migrations 001/002 |
| Transaction intelligence | partial inspector | wallet/transaction-related routes | trace/provider | transaction metadata | Provider-dependent | PARTIAL | `GraphInspector.tsx`, provider methods |
| Graph | `GraphInspector` with controls | graph/paths/metrics/layout | graph engine + projection | graph_edges/trace_runs; Neo4j projection | PostgreSQL yes; Neo4j unavailable | PARTIAL | `graph_engine.py`, `graph_projection.py` |
| Primary path | Highlighting/summary | `/primary-path` | `primary_path.py` | persisted trace/path projection | Yes for persisted traces | PASS | directed path tests and hardcoded cases |
| Fund flow | `FundFlowWorkspace` | graph/trace APIs | trace/path logic | trace/graph rows | Yes | PASS | `App.tsx`, `pages.tsx` |
| Patterns | `PatternsPage` | analyze/list/summary/detail | `PatternService`/`PatternEngine` | pattern tables | Trace-derived | PASS | `pattern_engine.py`, tests |
| Risk intelligence | `RiskPage`, overlay | assess/history/delta/factors | `RiskService`/`RiskEngine` | risk tables/joins | Trace-derived | PASS with integrity warning | `risk_engine.py`, `/system/integrity` |
| Realtime retracing | monitoring pages/SSE client | webhooks, simulated events, watches, stream | `RealtimeService`, EventBus | realtime/watch/application/attempt tables | Simulated locally; live not configured | PARTIAL/SIMULATED | `realtime_service.py`, `/realtime/health` |
| Entities/VASP | entities/attribution views | catalog/entity/address/case routes | attribution resolver | entities/attribution tables | Curated/static | PARTIAL | `attribution.py`, `synthetic_attribution.py` |
| Cross-chain | `CrossChainPage` | observations/analyze/links/paths | `CrossChainService` | migrations 008/019 | Requires observations/providers | PARTIAL | `cross_chain_service.py` |
| Threat intelligence | Limited/capability surface | sources/indicators/contracts | cyber persistence | cyber tables | No configured feed | PARTIAL/NOT CONFIGURED | `cyber_intelligence.py`, status |
| Sanctions | no complete connected page | screening/sync/status routes | cyber persistence | sanctions/screening tables | Zero local records | NOT CONFIGURED | `/intelligence/sanctions/status` |
| Evidence | ledger/manifest panel | evidence/manifest/custody routes | evidence service | evidence/manifest/custody | Yes for populated records | PARTIAL | `EvidenceLedgerPanel.tsx`, migration 014 |
| Timeline | timeline view | `/timeline` | realtime/report/workflow services | `investigation_timeline` | Yes | PASS | `main.py`, migration 007 |
| Reports | `ReportsPage` | generate/list/get/PDF | `ReportService`, ReportLab | `investigation_reports` | Yes when upstream populated | PARTIAL | `report_service.py`, `report_pdf.py` |
| SAHYOG | intake option/status label | no external connector | none | external reference field only | No | SIMULATED | `ConnectedIntake.tsx`, docs |
| NCRP | intake option/status label | no external connector | none | external reference field only | No | SIMULATED | `ConnectedIntake.tsx`, docs |
| Alchemy | indirect through intake/wallet views | historical/RPC methods | `AlchemyEthereumProvider` | persisted normalized data | Local probe connected | PASS/PARTIAL | `provider.py`, system status |
| TronGrid | chain selector boundary | provider/registry | `TronGridProvider` | chain-aware schema | Local key missing | NOT CONFIGURED | `provider.py`, system status |
| Neo4j | no direct full UI query | project/neighbors/shortest-path/status | `GraphProjectionService` | optional graph store | Local unavailable | PARTIAL/BLOCKED | `neo4j_client.py`, graph status |
| PostgreSQL | all case data surfaces | repository | asyncpg | canonical store | Connected; integrity WARN | PARTIAL | `/health`, `/system/integrity` |
| APK | none | mobile API boundary | server delegates to shared services | same canonical store | No native client | NOT PRESENT | no Gradle/manifest/mobile project |

## API route family matrix

| Route family | Representative routes | Status |
|---|---|---|
| Health/dependencies | `/health`, `/api/v1/system/status`, `/api/v1/system/integrity`, `/api/v1/providers` | PASS; reports degraded dependencies accurately |
| Case lifecycle | `/api/v1/cases`, `/cases/{id}/open`, `/close`, `/reopen`, `/status` | PASS at API level |
| Trace/graph | `/cases/{id}/traces`, `/graph`, `/graph/paths`, `/primary-path`, layout routes | PASS/PARTIAL depending Neo4j projection |
| Intelligence | `/entities`, attribution, cyber, sanctions, patterns, risk | PASS/PARTIAL based source configuration |
| Realtime | watches, signed webhook, simulated events, SSE, replay | SIMULATED/NOT CONFIGURED for live path |
| Evidence/reports | evidence, manifests, custody, reports, PDF | PASS/PARTIAL based case data |
| Cross-chain | observations, analyze, links, patterns, paths, timeline | PARTIAL; correlation requires explicit observations |
| Mobile boundary | `/api/v1/mobile/*` | PASS as API boundary; no client |

## Test coverage matrix

| Test group | Result | What it establishes |
|---|---:|---|
| Backend full suite | 92 passed, 3 skipped | unit/contract/service behavior across trace, graph, risk, realtime, evidence, providers and persistence contracts |
| Frontend Vitest | 1 passed | basic app rendering/component smoke coverage only |
| Frontend build | passed | TypeScript compilation and Vite production bundle |
| Runtime HTTP smoke | passed for health/status/integrity/status routes | process starts and returns dependency-aware responses |
| Runtime data snapshot | verified | hardcoded cases persist one path and known endpoint; not a substitute for live integration testing |

## Overall status

| Overall area | Status |
|---|---|
| Historical investigation core | PASS |
| Development demonstration | PASS |
| Production identity/security | BLOCKED |
| Live multi-chain operations | PARTIAL |
| Live realtime | NOT CONFIGURED |
| External sanctions/threat feeds | NOT CONFIGURED |
| Neo4j projection runtime | BLOCKED in audited environment |
| Native mobile | NOT PRESENT |
