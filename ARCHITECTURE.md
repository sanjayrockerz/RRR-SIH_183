# Architecture

The repository is a modular monolith. FastAPI owns HTTP contracts and application orchestration; domain models do not import provider SDKs. BlockchainProvider and BlockchainDataFabric are the infrastructure boundary. Alchemy is an adapter only.

Flow: React → FastAPI → application services → repository interfaces → PostgreSQL, with tracing continuing through BlockchainProvider → normalized transfers → bounded NetworkX MultiDiGraph → paths/flows/metrics → persisted trace runs/transactions/edges/evidence.

Cases, wallets, and blockchain transactions are independent records linked through case relationships. Trace runs are first-class records; graph edges reference a specific run while retaining canonical transaction, transfer, and evidence links. NetworkX is rebuilt for analysis and is never serialized as the source of truth.

The trace engine supports bounded forward and backward traversal, time and asset filters, asset-local thresholds, shortest paths, observed fund flows, and descriptive graph metrics. Entity attribution, cross-chain correlation, live monitoring, ML risk, and automated external workflows are not implemented.
## Behavioral pattern intelligence

Phase 5 adds an explicit `PatternService` and modular `PatternEngine` over bounded `TraceResult` data. Detector output is persisted as explainable, evidence-linked `PatternObservation` records through migration `005_fraud_patterns.sql`. The engine is descriptive only; future risk scoring remains a separate `RiskEngine` boundary.
