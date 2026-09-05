# RRR-Realtime Capability Gap Analysis

This document provides a systematic gap analysis mapping the current **RRR-Realtime** codebase against SIH Problem Statement 183 requirements and industry-standard cryptocurrency fraud investigation specifications.

---

## 1. Classification Matrix

Each capability is classified as:
- **`IMPLEMENTED`**: Production-ready, backend-persisted, fully integrated with UI and API tests.
- **`PARTIAL`**: Architectural boundary exists with working local logic, but depends on unconfigured external data/credentials or requires broader feature completion.
- **`MOCKED`**: Explicit simulation layer or non-functional placeholder state rendered in UI to reflect unintegrated external portals.
- **`MISSING`**: Capability not yet implemented or designed in the current codebase.

| # | Operational Domain / Capability | Status | Detailed Implementation & Gap State |
| :--- | :--- | :--- | :--- |
| **1** | **Wallet Ingestion** | `IMPLEMENTED` | Case intake API accepts target addresses for Ethereum (0x) and TRON (Base58). Normalization handles case-insensitivity for Ethereum and case-sensitivity for TRON. |
| **2** | **Blockchain Tracing** | `IMPLEMENTED` | Alchemy Ethereum adapter fetches native ETH and ERC-20 transfers. TronGrid adapter handles TRON TRX/TRC-20 transfers. Provider fallback and capabilities exposed via API. |
| **3** | **Multi-Hop Tracing** | `IMPLEMENTED` | Forward and backward multi-hop traversal with depth limits, asset filtering, min-amount thresholds, and hop-by-hop persistence. |
| **4** | **VASP Attribution** | `PARTIAL` | Migration `017` introduces a curated VASP registry (`curated_vasps`), entity provenance metadata, and confidence scores. Missing automated commercial VASP data feed ingestion (e.g. Chainalysis/TRM/Elliptic). |
| **5** | **Nearest-VASP Identification** | `PARTIAL` | NetworkX shortest path traversal can find paths to known VASP addresses in the graph, but lacks automated clustering algorithms (e.g. deposit address reuse clustering). |
| **6** | **Fund-Flow Analysis** | `IMPLEMENTED` | Direct and indirect fund flow metrics, token balance changes, flow volume aggregation, and path centrality calculations in `graph_engine.py`. |
| **7** | **Cross-Chain Tracing** | `PARTIAL` | Chain-qualified node identity (`ethereum:0x...`, `tron:T...`), persistent cross-chain links, and UI visualizer. TRON tracing requires live `TRONGRID_API_KEY`. |
| **8** | **Bridge Detection** | `PARTIAL` | Data-driven bridge definitions (`bridge_definitions` table) with correlation confidence scoring. Missing live cross-chain messaging state verification (e.g. LayerZero/Wormhole payload decoding). |
| **9** | **Mixer Detection** | `IMPLEMENTED` | Pattern engine identifies known mixer pool interactions (e.g., Tornado Cash, Railgun, Blender) and flags rapid split/merge behaviors. |
| **10** | **Fraud Typologies** | `IMPLEMENTED` | Phase 5 `PatternEngine` evaluates 8 explainable typologies: Rapid Hop, Peel Chain, Fan-In, Fan-Out, Consolidation, Burst Activity, Dormant Activation, and Mixer/Bridge Exposure. |
| **11** | **Risk Scoring** | `IMPLEMENTED` | Phase 6 `RiskEngine` generates quantitative scores (0–100), risk bands (`LOW` to `CRITICAL`), factor contribution breakdowns, and versioned risk deltas. |
| **12** | **Alerts** | `IMPLEMENTED` | Evidence-linked `RiskAlertCandidate` and `Alert` models with investigator state transitions (`ACKNOWLEDGED`, `DISMISSED`, `ESCALATED`) and review logs. |
| **13** | **Multi-Victim Correlation** | `PARTIAL` | `GET /api/v1/cases/{id}/related` identifies exact wallet address overlaps across cases. Missing fuzzy graph similarity matching and shared deposit cluster correlation. |
| **14** | **Evidence Preservation** | `IMPLEMENTED` | SHA-256 canonical hashing of on-chain observations, deterministic Merkle-like manifest trees, and append-only chain-of-custody event tracking. |
| **15** | **Report Generation** | `IMPLEMENTED` | `ReportService` & `ReportPDF` generate evidence-backed PDF report snapshots with content hashes, executive summaries, graph metrics, and strict limitations disclaimers. |
| **16** | **NCRP Integration Boundary** | `MOCKED` | Indian National Cyber Crime Reporting Portal (NCRP) API interface is mocked/simulated. UI displays explicit "Simulated / Not Connected" status. |
| **17** | **Sahyog Integration Boundary** | `MOCKED` | MHA SAHYOG portal integration interface is simulated. No live API credentials or state exchange configured. |
| **18** | **Investigator Workflow** | `IMPLEMENTED` | Full React workstation with dashboard, intake wizard, visual graph inspector, timeline view, evidence ledger, alert management, and PDF report export. |
| **19** | **API Integration** | `IMPLEMENTED` | Complete FastAPI REST API with Pydantic contract validation, CORS middleware, request ID tracking, and standardized error envelopes. |
| **20** | **AI / ML Intelligence** | `MISSING` | No Machine Learning, Graph Neural Networks (GNN), or AI LLM copilot models are currently connected. Risk & pattern scoring is 100% rule-based and deterministic. |

---

## 2. Detailed Domain Gap Descriptions

### A. VASP Attribution & Clustering
- **Current State**: Static curated list in migration `017_curated_vasp_and_graph_layout.sql` and manual attribution insertion endpoints.
- **Gap**: High-throughput automated ingestion of VASP cluster tags (e.g. Binance deposit address clusters, Coinbase hot wallets) and Travel Rule data.

### B. Indian Cybercrime Portals (NCRP / SAHYOG)
- **Current State**: UI indicators show simulated NCRP/SAHYOG data feeds to demonstrate workflow readiness.
- **Gap**: Production API integration with MHA/NCRP REST web services for automated complaint intake, acknowledgement token generation, and notice issuing.

### C. Advanced Multi-Victim Graph Correlation
- **Current State**: Cross-case matching relies on 100% exact address string matches (`/api/v1/cases/{id}/related`).
- **Gap**: Graph isomorphism and co-spending transaction input heuristics (e.g. Common Input Ownership Heuristic) across distinct investigative cases.

### D. AI / Machine Learning Capabilities
- **Current State**: All threat scoring and pattern identification rely on explicit deterministic rules in `pattern_engine.py` and `risk_engine.py`.
- **Gap**: Graph Convolutional Networks (GCN) for unlabelled wallet clustering, anomaly detection models for novel laundering typologies, and LLM-assisted investigative report summarization.
