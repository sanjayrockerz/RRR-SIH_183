# RRR-Realtime Future Phase Implementation Roadmap

This document outlines the recommended sequential implementation roadmap for future development phases of the **RRR-Realtime** platform (SIH Problem Statement 183).

---

## 1. Strict Architectural Rule & Layering Governance

Every phase MUST strictly observe and preserve the conceptual boundary hierarchy:

```
[ FACT ] ──► [ ATTRIBUTION ] ──► [ BEHAVIOR ] ──► [ RISK ] ──► [ RECOMMENDATION ]
```

1. **FACT**: On-chain data is canonical and immutable. Raw transaction inputs/outputs are never altered.
2. **ATTRIBUTION**: Entity tags must retain explicit source provenance, dataset versions, and confidence ratings.
3. **BEHAVIOR**: Derived transaction patterns remain descriptive observations backed by on-chain transfer evidence.
4. **RISK**: Quantitative risk scores prioritize investigative attention; they do not assert legal criminality.
5. **RECOMMENDATION**: Suggested actions guide investigator decisions; automated fund freezes or asset transfers are never executed autonomously.

---

## 2. Sequential Phase Roadmap

```
+-----------------------------------------------------------------------------------+
| Phase 1: Stabilization, Testing & Database Hardening                             |
+-----------------------------------------------------------------------------------+
                                         │
                                         ▼
+-----------------------------------------------------------------------------------+
| Phase 2: Production VASP Attribution & Nearest-VASP Clustering Engine             |
+-----------------------------------------------------------------------------------+
                                         │
                                         ▼
+-----------------------------------------------------------------------------------+
| Phase 3: Multi-Victim Correlation & Cross-Case Graph Intelligence                 |
+-----------------------------------------------------------------------------------+
                                         │
                                         ▼
+-----------------------------------------------------------------------------------+
| Phase 4: Distributed Real-Time Webhook Worker Queue & Reorg Engine                |
+-----------------------------------------------------------------------------------+
                                         │
                                         ▼
+-----------------------------------------------------------------------------------+
| Phase 5: NCRP & SAHYOG Indian Cybercrime Portal Integration                       |
+-----------------------------------------------------------------------------------+
                                         │
                                         ▼
+-----------------------------------------------------------------------------------+
| Phase 6: Production Authentication, RBAC & Immutable Audit Security              |
+-----------------------------------------------------------------------------------+
                                         │
                                         ▼
+-----------------------------------------------------------------------------------+
| Phase 7: Neo4j Graph Synchronization & Cypher Traversal Engine                    |
+-----------------------------------------------------------------------------------+
                                         │
                                         ▼
+-----------------------------------------------------------------------------------+
| Phase 8: Advanced Machine Learning & AI Intelligence                              |
+-----------------------------------------------------------------------------------+
```

---

## 3. Phase Breakdown & Objectives

### 🔹 Phase 1: Stabilization, Testing & Database Hardening
- **Objective**: Fix test suite dependencies, add missing database performance indexes, and enforce atomic database transactions.
- **Key Tasks**:
  1. Refactor `test_runtime_open_case.py` to use FastAPI `TestClient(app)` with ASGI transport so tests pass self-contained without an external server process.
  2. Add Migration `020_performance_indexes.sql` creating missing indexes on `cross_chain_links`, `graph_edges`, `case_timeline_events`, and `evidence_records`.
  3. Wrap multi-table persistence calls in `persistence.py` within explicit async transaction blocks (`async with pool.acquire() as conn: async with conn.transaction():`).

### 🔹 Phase 2: Production VASP Attribution & Nearest-VASP Clustering Engine
- **Objective**: Expand entity attribution with automated VASP clustering and deposit address identification.
- **Key Tasks**:
  1. Build an automated ingestion pipeline for public/commercial VASP attribution feeds with version tracking.
  2. Implement Common Input Ownership Heuristic (CIOH) clustering to group wallet addresses owned by the same exchange/VASP.
  3. Develop a Nearest-VASP Path Finder returning the shortest hop count and fund flow path from a victim wallet to an exchange deposit endpoint.

### 🔹 Phase 3: Multi-Victim Correlation & Cross-Case Graph Intelligence
- **Objective**: Identify shared criminal infrastructure across multiple independent investigative cases.
- **Key Tasks**:
  1. Implement multi-case graph overlap analysis (`POST /api/v1/cases/correlate`).
  2. Detect shared deposit addresses, common laundering intermediaries, and syndicate wallets serving multiple victims.
  3. Render cross-case correlation matrix and cluster views in the investigator workstation UI.

### 🔹 Phase 4: Distributed Real-Time Webhook Worker Queue & Reorg Engine
- **Objective**: Provide high-throughput, fault-tolerant real-time webhook ingestion.
- **Key Tasks**:
  1. Integrate Redis + ARQ (or Celery) distributed task queue for asynchronous webhook event processing.
  2. Implement automatic exponential backoff retry scheduling for failed webhook deliveries.
  3. Develop automatic blockchain reorg reconciliation to rollback invalidated graph edges on block depth re-orgs.

### 🔹 Phase 5: NCRP & SAHYOG Indian Cybercrime Portal Integration
- **Objective**: Establish live integration boundaries with Indian national cybercrime portals.
- **Key Tasks**:
  1. Replace simulated NCRP endpoints with production REST API client wrappers for complaint intake and case updates.
  2. Implement SAHYOG notice intake and exchange coordination interfaces with cryptographic signature verification.
  3. Add standardized Indian cybercrime report export formats in `ReportPDF`.

### 🔹 Phase 6: Production Authentication, RBAC & Immutable Audit Security
- **Objective**: Enforce strict access control, identity governance, and tamper-evident audit logs.
- **Key Tasks**:
  1. Enable mandatory JWT verification with OpenID Connect (OIDC) / Keycloak integration.
  2. Enforce Role-Based Access Control (RBAC): `ANALYST` (view only), `INVESTIGATOR` (case/trace management), `SUPERVISOR` (report/case approval), `ADMIN`.
  3. Digitally sign PDF reports and evidence manifests using X.509 RSA/ECDSA investigator certificates.

### 🔹 Phase 7: Neo4j Graph Synchronization & Cypher Traversal Engine
- **Objective**: Enable sub-second Cypher queries over massive multi-million node transaction graphs.
- **Key Tasks**:
  1. Implement reliable CDC (Change Data Capture) or background worker sync from PostgreSQL to Neo4j.
  2. Add backend Cypher query execution services (`GET /api/v1/graph/cypher`).
  3. Implement advanced graph pattern matching (e.g., circular laundering loops, complex split-merge paths).

### 🔹 Phase 8: Advanced Machine Learning & AI Intelligence
- **Objective**: Augment investigator capabilities with machine learning models.
- **Key Tasks**:
  1. Train Graph Convolutional Networks (GCN) for unlabelled wallet risk classification and anomaly detection.
  2. Integrate an air-gapped LLM Copilot for natural language graph querying ("Find all payments from wallet X to exchange Y in May") and executive report summarization.
