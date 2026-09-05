# RRR-Realtime Architecture Audit

## 1. System Overview & Architectural Paradigm

**RRR-Realtime** is a production-oriented crypto-fraud intelligence and multi-hop transaction tracing platform designed for law enforcement, cybercrime investigators, and intelligence analysts.

The application follows a **Modular Monolith** architecture:
- **Backend API (`apps/api`)**: Python 3.13 / FastAPI framework. Handles HTTP routing, domain logic, on-chain graph analysis via NetworkX, deterministic pattern detection, evidence ledger generation, and risk scoring.
- **Frontend Workstation (`apps/investigator-web`)**: React 18 / TypeScript / Vite Single Page Application (SPA). Provides an interactive investigative dashboard, case intake, multi-hop graph visualization, evidence review, and risk/pattern inspection.
- **Relational Source of Truth**: PostgreSQL database managing cases, wallets, normalized transactions, trace runs, pattern observations, risk assessments, evidence manifests, and audit trails across 19 ordered SQL migrations.
- **Property Graph Boundary**: Optional Neo4j graph storage for high-performance Cypher-based graph queries and relationship traversal.
- **Blockchain Data Fabric**: Provider-independent adapter layer supporting **Alchemy** (Ethereum mainnet historical and webhook Activity API) and **TronGrid** (TRON network historical TRC-20/TRX transfers).

```
 +-----------------------------------------------------------------------+
 |                     Investigator Web Application                      |
 |                      (React + TypeScript + Vite)                      |
 +-----------------------------------+-----------------------------------+
                                     | REST API (JSON)
                                     v
 +-----------------------------------------------------------------------+
 |                     FastAPI API Server Monolith                       |
 |  +-------------------+  +--------------------+  +------------------+  |
 |  |    CaseService    |  |    TraceService    |  |  PatternEngine   |  |
 |  +-------------------+  +--------------------+  +------------------+  |
 |  |    RiskEngine     |  |  EvidenceLedger    |  |  RealtimeService |  |
 |  +-------------------+  +--------------------+  +------------------+  |
 |  | CrossChainService |  | CyberIntelProvider |  |   ReportService  |  |
 |  +-------------------+  +--------------------+  +------------------+  |
 +---------------+-------------------+-------------------+---------------+
                 |                   |                   |
                 v                   v                   v
     +-------------------+   +---------------+   +---------------+
     |    PostgreSQL     |   |     Neo4j     |   | Alchemy/Tron  |
     | (Source of Truth) |   | (Opt. Graph)  |   | Blockchain RPC|
     +-------------------+   +---------------+   +---------------+
```

---

## 2. Strict Architectural Taxonomy

The system enforces strict operational and conceptual separation across five domains:

1. **FACT**: Directly observed, immutable on-chain transactions, block timestamps, transfer amounts, gas costs, and raw RPC payloads.
2. **ATTRIBUTION**: Source-backed entity and VASP associations backed by clear provenance, dataset versions, and confidence scores.
3. **BEHAVIOR**: Derived transaction patterns (e.g., rapid-hop, peel chain, fan-out, mixer interaction) identified by deterministic rule engines over bounded traces.
4. **RISK**: Quantitative, evidence-backed priority scores and risk bands derived deterministically from weighted factor models.
5. **RECOMMENDATION**: Suggested investigator actions (e.g., watch wallet, request exchange freeze, generate report) that never execute fund transfers or false claims of criminality.

---

## 3. Core Component & Service Boundaries

### Backend Modules (`apps/api/app/`)

- [main.py](file:///c:/Users/Rakshan%20M/Downloads/RRR-SIH_183-main%20%281%29/RRR-SIH_183-main/apps/api/app/main.py): FastAPI application initialization, middleware (CORS, Request ID, Error Handling), dependency injection, and REST route handlers.
- [domain.py](file:///c:/Users/Rakshan%20M/Downloads/RRR-SIH_183-main%20%281%29/RRR-SIH_183-main/apps/api/app/domain.py): Pydantic v2 data structures, Enums (`Chain`, `DataMode`, `CapabilityStatus`, `RiskBand`, `PatternType`), request/response validation contracts.
- [services.py](file:///c:/Users/Rakshan%20M/Downloads/RRR-SIH_183-main%20%281%29/RRR-SIH_183-main/apps/api/app/services.py): Core application orchestration (`CaseService`, `TraceService`, `WalletIntelligenceService`).
- [provider.py](file:///c:/Users/Rakshan%20M/Downloads/RRR-SIH_183-main%20%281%29/RRR-SIH_183-main/apps/api/app/provider.py) & [provider_registry.py](file:///c:/Users/Rakshan%20M/Downloads/RRR-SIH_183-main%20%281%29/RRR-SIH_183-main/apps/api/app/provider_registry.py): `BlockchainProvider` interface implementations (`AlchemyEthereumProvider`, `TronGridProvider`, `FixtureProvider`).
- [graph_engine.py](file:///c:/Users/Rakshan%20M/Downloads/RRR-SIH_183-main%20%281%29/RRR-SIH_183-main/apps/api/app/graph_engine.py): NetworkX `MultiDiGraph` builder, path traversal algorithms, fund-flow aggregation, and graph centrality metrics.
- [pattern_engine.py](file:///c:/Users/Rakshan%20M/Downloads/RRR-SIH_183-main%20%281%29/RRR-SIH_183-main/apps/api/app/pattern_engine.py) & [pattern_service.py](file:///c:/Users/Rakshan%20M/Downloads/RRR-SIH_183-main%20%281%29/RRR-SIH_183-main/apps/api/app/pattern_service.py): Fraud typology rule engines (rapid hop, peel chain, fan-in/fan-out, consolidation, mixer/bridge interactions).
- [risk_engine.py](file:///c:/Users/Rakshan%20M/Downloads/RRR-SIH_183-main%20%281%29/RRR-SIH_183-main/apps/api/app/risk_engine.py) & [risk_service.py](file:///c:/Users/Rakshan%20M/Downloads/RRR-SIH_183-main%20%281%29/RRR-SIH_183-main/apps/api/app/risk_service.py): Deterministic risk scoring engine, factor evaluation, score cap enforcement, risk deltas, and alert candidate generation.
- [realtime_service.py](file:///c:/Users/Rakshan%20M/Downloads/RRR-SIH_183-main%20%281%29/RRR-SIH_183-main/apps/api/app/realtime_service.py) & [realtime_persistence.py](file:///c:/Users/Rakshan%20M/Downloads/RRR-SIH_183-main%20%281%29/RRR-SIH_183-main/apps/api/app/realtime_persistence.py): Webhook signature verification, idempotent event recording, dead-letter queue, and background reassessment triggers.
- [cross_chain_service.py](file:///c:/Users/Rakshan%20M/Downloads/RRR-SIH_183-main%20%281%29/RRR-SIH_183-main/apps/api/app/cross_chain_service.py) & [cross_chain.py](file:///c:/Users/Rakshan%20M/Downloads/RRR-SIH_183-main%20%281%29/RRR-SIH_183-main/apps/api/app/cross_chain.py): Chain-qualified node identity (`ethereum:0x...`, `tron:T...`), bridge correlation definitions, and cross-chain trace linkage.
- [evidence_ledger.py](file:///c:/Users/Rakshan%20M/Downloads/RRR-SIH_183-main%20%281%29/RRR-SIH_183-main/apps/api/app/evidence_ledger.py) & [evidence_service.py](file:///c:/Users/Rakshan%20M/Downloads/RRR-SIH_183-main%20%281%29/RRR-SIH_183-main/apps/api/app/evidence_service.py): Canonical SHA-256 evidence observation hashing, deterministic manifest trees, and append-only custody event logs.
- [report_service.py](file:///c:/Users/Rakshan%20M/Downloads/RRR-SIH_183-main%20%281%29/RRR-SIH_183-main/apps/api/app/report_service.py) & [report_pdf.py](file:///c:/Users/Rakshan%20M/Downloads/RRR-SIH_183-main%20%281%29/RRR-SIH_183-main/apps/api/app/report_pdf.py): ReportLab PDF generation engine producing evidence-backed investigative report snapshots.
- [cyber_intelligence.py](file:///c:/Users/Rakshan%20M/Downloads/RRR-SIH_183-main%20%281%29/RRR-SIH_183-main/apps/api/app/cyber_intelligence.py): Exact chain-aware sanctions screening, threat indicator matching, and contract security audit storage.
- [graph/](file:///c:/Users/Rakshan%20M/Downloads/RRR-SIH_183-main%20%281%29/RRR-SIH_183-main/apps/api/app/graph/): Neo4j graph projection layer for syncing nodes, relationships, and evidence attributes into Neo4j property graphs.

---

## 4. Data Flows & Execution Lifecycles

### A. Case Intake & Tracing Flow
1. **Intake**: Investigator creates a case (`POST /api/v1/cases`) and registers victim target wallet addresses (`POST /api/v1/cases/{id}/wallets`).
2. **Trace Request**: Investigator initiates a multi-hop trace (`POST /api/v1/cases/{id}/traces`) specifying seed address, chain (`ethereum`/`tron`), direction (`FORWARD`/`BACKWARD`), max depth (e.g. 5 hops), and asset/time bounds.
3. **Data Acquisition**: `TraceService` calls `BlockchainDataFabric` -> `BlockchainProvider` (Alchemy or TronGrid). On-chain transfers are fetched and normalized into canonical `Transfer` domain models.
4. **Graph Construction**: Normalized transfers are loaded into `NetworkXGraphEngine`, creating a `MultiDiGraph` where nodes represent wallet addresses and edges represent transfer events with token, amount, timestamp, and transaction hash.
5. **Persistence**: Transactions, graph edges, nodes, and trace run metadata are atomically persisted in PostgreSQL.
6. **Pattern Analysis**: `PatternEngine` evaluates graph topology to detect rapid hops, peel chains, fan-outs, and mixer touches, recording `PatternObservation` records.
7. **Risk Assessment**: `RiskEngine` calculates quantitative risk scores (0–100) and risk bands based on pattern observations, attribution tags, and transaction characteristics.
8. **Evidence Hashing**: `EvidenceLedger` computes canonical SHA-256 content hashes for all observations and commits them to the evidence ledger.

### B. Real-Time Webhook Processing Flow
```
Alchemy Webhook Event
       │
       ▼
POST /api/v1/webhooks/alchemy
       │
       ├─► Verify HMAC Signature (Header)
       │
       ├─► Deduplicate in PostgreSQL (`realtime_events` table)
       │
       ├─► Store Processing Attempt (`realtime_processing_attempts`)
       │
       ├─► Update Case Transactions & Edges (Idempotent)
       │
       ├─► Re-trigger Pattern Engine & Risk Engine
       │
       └─► Publish Audit Event & Webhook Status (RETRY_PENDING / PROCESSED / DEAD_LETTER)
```

---

## 5. Database Schema & Migration Architecture

PostgreSQL serves as the primary source of truth across 19 ordered migrations ([infrastructure/postgres](file:///c:/Users/Rakshan%20M/Downloads/RRR-SIH_183-main%20%281%29/RRR-SIH_183-main/infrastructure/postgres)):

| Migration File | Primary Domain / Purpose | Key Tables Created / Modified |
| :--- | :--- | :--- |
| `001_initial.sql` | Cases & Target Wallets | `investigation_cases`, `case_wallets` |
| `002_blockchain_data_fabric.sql` | Normalized Transactions & Addresses | `blockchain_addresses`, `normalized_transactions`, `native_transfers` |
| `003_trace_runs.sql` | First-Class Trace Runs & Graph Edges | `trace_runs`, `graph_nodes`, `graph_edges` |
| `004_entity_attribution.sql` | Entity & VASP Attribution | `entities`, `entity_attributions` |
| `005_fraud_patterns.sql` | Fraud Typology Observations | `pattern_observations` |
| `006_risk_intelligence.sql` | Risk Engine Scores & Alerts | `risk_assessments`, `risk_factors`, `risk_alert_candidates` |
| `007_realtime_retracing.sql` | Real-Time Intake & Watch Targets | `realtime_events`, `case_watch_targets` |
| `008_cross_chain_intelligence.sql` | Cross-Chain Links & Bridges | `cross_chain_nodes`, `cross_chain_links`, `bridge_definitions` |
| `009_backend_integration.sql` | Case Lifecycle Metadata | `investigation_cases` (added `status`, `reopened_at`, `closed_at`) |
| `010_entity_provenance.sql` | Attribution Datasets | `attribution_sources` |
| `011_cyber_intelligence.sql` | Threat & Sanctions Intelligence | `sanctions_records`, `threat_indicators`, `cyber_screening_runs` |
| `012_realtime_operations.sql` | Webhook Queue State | `realtime_processing_attempts` |
| `013_alert_operations.sql` | Alert Workflow State | `alerts`, `alert_reviews` |
| `014_evidence_ledger.sql` | Integrity Manifests & Custody | `evidence_records`, `evidence_manifests`, `chain_of_custody_events` |
| `015_investigation_reports.sql` | Report Snapshots | `investigation_reports` |
| `016_case_workflow.sql` | Operational Case Timelines | `case_timeline_events` |
| `017_curated_vasp_and_graph_layout.sql` | Curated VASP Registry & Node Positions | `curated_vasps`, `graph_node_positions` |
| `018_trace_runs_acquisition.sql` | Trace Execution Metadata | `trace_runs` (added `acquisition_mode`, `provider_status`) |
| `019_cross_chain_transfer_fields.sql` | Cross-Chain Transfers | `cross_chain_links` (added `source_transfer_id`, `target_transfer_id`) |

---

## 6. Frontend Architecture & Workstation Layout

The React 18 workstation ([apps/investigator-web/src](file:///c:/Users/Rakshan%20M/Downloads/RRR-SIH_183-main%20%281%29/RRR-SIH_183-main/apps/investigator-web/src)) is structured into intuitive operational workspaces:

- [App.tsx](file:///c:/Users/Rakshan%20M/Downloads/RRR-SIH_183-main%20%281%29/RRR-SIH_183-main/apps/investigator-web/src/App.tsx): Main application state container, active tab navigator, header status indicators, and notification toaster.
- [pages.tsx](file:///c:/Users/Rakshan%20M/Downloads/RRR-SIH_183-main%20%281%29/RRR-SIH_183-main/apps/investigator-web/src/pages.tsx): Modular view components:
  1. **DashboardWorkspace**: High-level platform statistics, active cases, top risk alerts, system provider statuses.
  2. **CasesWorkspace**: Case intake, search, filtering, status modification, and target wallet registration.
  3. **GraphWorkspace**: Interactive visual multi-hop graph inspector with node inspection, path highlighting, and fund-flow breakdowns.
  4. **PatternWorkspace**: Typology observation list, explainable rule triggers, and timeline alignment.
  5. **RiskWorkspace**: Qualitative risk scores, factor contribution radar, risk history deltas, and alert review queues.
  6. **EvidenceWorkspace**: Hash integrity verification, manifest tree inspector, and chain of custody logs.
  7. **CrossChainWorkspace**: Multi-chain bridge connection analyzer and cross-chain link confidence scores.
  8. **RealtimeOperationsWorkspace**: Webhook delivery queue, event inspection, retry state, and dead-letter replay controls.
  9. **ReportsWorkspace**: Immutable PDF snapshot creation, preview, and download center.
- [api.ts](file:///c:/Users/Rakshan%20M/Downloads/RRR-SIH_183-main%20%281%29/RRR-SIH_183-main/apps/investigator-web/src/api.ts): Strongly typed API client handling REST calls to FastAPI backend with standard error envelopes.
