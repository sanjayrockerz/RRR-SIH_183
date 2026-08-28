# Architecture

The repository is a modular monolith. FastAPI owns HTTP contracts and application orchestration; domain models do not import provider SDKs. BlockchainProvider and BlockchainDataFabric are the infrastructure boundary. Alchemy is an adapter only.

Flow: React → FastAPI → application services → repository interfaces → PostgreSQL, with tracing continuing through BlockchainProvider → normalized transfers → bounded NetworkX MultiDiGraph → paths/flows/metrics → persisted trace runs/transactions/edges/evidence.

Cases, wallets, and blockchain transactions are independent records linked through case relationships. Trace runs are first-class records; graph edges reference a specific run while retaining canonical transaction, transfer, and evidence links. NetworkX is rebuilt for analysis and is never serialized as the source of truth.

The trace engine supports bounded forward and backward traversal, time and asset filters, asset-local thresholds, shortest paths, observed fund flows, and descriptive graph metrics. Entity attribution, cross-chain correlation, live monitoring, ML risk, and automated external workflows are not implemented.

The Wallet Intelligence read model is a read-only projection over persisted wallet identity, graph edges, case relationships, transactions, and evidence. It does not query a provider for live balance and does not infer ownership or criminality. Ethereum addresses are normalized case-insensitively; Tron Base58 addresses remain case-sensitive.
## Behavioral pattern intelligence

Phase 5 adds an explicit `PatternService` and modular `PatternEngine` over bounded `TraceResult` data. Detector output is persisted as explainable, evidence-linked `PatternObservation` records through migration `005_fraud_patterns.sql`. The engine is descriptive only; future risk scoring remains a separate `RiskEngine` boundary.

Phase 6 adds deterministic `RiskEngine` assessment over persisted patterns, source-backed attribution, and trace evidence. `RiskAssessment` records are immutable/versioned, factors require evidence references, deltas are explicit, and reviewable alert candidates do not imply fraud. See [risk-intelligence.md](docs/architecture/risk-intelligence.md).
## Phase 7 — Real-time retracing

Realtime events enter through a signed provider adapter, are deduplicated in PostgreSQL, and update existing transactions, evidence, graph edges, patterns, risk assessments, timeline, and alert candidates. No polling loop or unsupported live claim is introduced.

## Phase 8 — Cross-chain intelligence

Cross-chain node identity is chain-qualified. Observed normalized transfers remain distinct from inferred bridge links, which carry correlation confidence, reasons, provenance, and evidence. Ethereum uses Alchemy; TronGrid is available as a bounded historical adapter but reports `NOT_CONFIGURED` without credentials. See [cross-chain-intelligence.md](docs/architecture/cross-chain-intelligence.md).

## Phase F - Cyber intelligence and sanctions

Cyber-intelligence sources, threat indicators, sanctions records, and contract-security findings are separate persisted domains. Exact address screening is available through `CyberIntelligenceProvider`; results preserve source, dataset version, explanation, and screening timestamp. With no approved records configured, the API returns `NOT_CONFIGURED`, never fabricated matches or a false clearance. See [threat-intelligence.md](docs/architecture/threat-intelligence.md).

## Realtime operations

Signed provider events are persisted before application. Processing attempts, retry-pending state, dead-letter state, and explicit replay are persisted through the repository boundary. Replays do not bypass event identity or case-application idempotency. See [realtime-operations.md](docs/architecture/realtime-operations.md).

## Alert operations

Generated alert candidates and alerts remain evidence-linked. Acknowledgement, dismissal, and escalation are explicit persisted workflow transitions with separate review history, audit events, and timeline entries. They do not alter the underlying observation or imply criminality. See [alert-operations.md](docs/architecture/alert-operations.md).

## Evidence ledger

Evidence observations can be hashed and grouped into deterministic manifests. Chain-of-custody events are append-only and reference the original evidence record. PostgreSQL remains the source of truth; the ledger is an integrity aid, not a court-certified export. See [evidence-ledger.md](docs/architecture/evidence-ledger.md).

## Investigative reports

Reports are immutable snapshots assembled by `ReportService` from persisted case, trace, pattern, risk, and evidence records. They retain source IDs and a content hash, and explicitly separate facts, observations, posture, evidence, and limitations. Report generation is not authenticated export until OIDC/RBAC and retention controls are enabled. See [investigative-reports.md](docs/architecture/investigative-reports.md).

## Cross-case intelligence

The related-case query exposes only exact overlaps in persisted wallet or transaction identity. It is a derived investigative lead, not proof of common control or criminality. See [cross-case-intelligence.md](docs/architecture/cross-case-intelligence.md).

## Authentication boundary

Authentication is an opt-in, backend-only JWT verification boundary. It accepts externally issued RS256/ES256 bearer tokens only when a trusted public key and `AUTH_REQUIRED=true` are configured. This does not yet provide case-level authorization or production SSO integration. See [authentication.md](docs/architecture/authentication.md).
