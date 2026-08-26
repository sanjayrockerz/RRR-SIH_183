# RRR-Realtime

## Reactive Tracing, Risk Registry and Prevention for Crypto Fraud using VASP

RRR-Realtime is a production-oriented crypto-fraud intelligence platform for authorized cybercrime, law-enforcement, and investigator workflows. It converts victim-reported wallet observations into bounded, evidence-backed transaction tracing and explainable behavioral intelligence.

The platform keeps facts, attribution, analysis, and future recommendations separate. It does not custody funds, sign transactions, claim criminality, or present behavioral patterns as proof of fraud.

## Solution features

- Persistent investigation cases, wallets, transactions, evidence, and trace runs.
- Provider-independent blockchain data fabric with an Alchemy Ethereum adapter.
- Canonical transaction and native/token transfer normalization.
- Bounded forward and backward transaction tracing with configurable limits.
- NetworkX multi-edge transaction graph with paths, flows, metrics, and evidence references.
- Source-backed entity and VASP attribution with confidence and provenance.
- Explainable Phase 5 behavioral patterns: rapid hop, fan-in/out, peel chain, consolidation, burst activity, dormant activation, mixer/bridge interaction, and entity exposure.
- Phase 6 deterministic investigative risk posture with configurable factors, risk bands, immutable assessment history, risk delta, investigative priority, watch-status readiness, and reviewable alert candidates.
- Investigator workstation UI with case intake, graph inspection, evidence references, and pattern intelligence.
- PostgreSQL source of truth with deterministic transaction, trace, and pattern deduplication.
- Explicit capability states for historical, simulated, live, unsupported, and not-configured integrations.

## Current capability boundary

The current release is historical Ethereum analysis through Alchemy. SAHYOG/NCRP, real-time ingestion, cross-chain tracing, ML risk scoring, authentication/SSO, and automated VASP communication are architectural extension points, not falsely represented live features.

## Quick start

1. Start PostgreSQL: `docker compose up -d postgres`.
2. Copy `.env.example` to `.env` and set `ALCHEMY_API_KEY`.
3. Start the API: `python -m venv .venv && .\.venv\Scripts\Activate.ps1 && pip install -r apps/api/requirements.txt && uvicorn app.main:app --reload --app-dir apps/api`.
4. Start the web app: `cd apps/investigator-web && npm install && npm run dev`.

The API uses PostgreSQL as its source of truth. On a fresh database, apply migrations in order: `001_initial.sql`, `002_blockchain_data_fabric.sql`, `003_trace_runs.sql`, `004_entity_attribution.sql`, `005_fraud_patterns.sql`, then `006_risk_intelligence.sql` from `infrastructure/postgres`. Attribution remains source-backed and does not establish ownership or criminal involvement.

## API

- `POST /api/v1/cases`
- `POST /api/v1/cases/{case_id}/wallets`
- `POST /api/v1/cases/{case_id}/transactions`
- `GET /api/v1/cases/{case_id}`
- `POST /api/v1/cases/{case_id}/traces`
- `GET /api/v1/provider/capabilities`
- `POST /api/v1/cases/{case_id}/patterns/analyze`
- `GET /api/v1/cases/{case_id}/patterns`
- `GET /api/v1/cases/{case_id}/patterns/summary`
- `POST /api/v1/cases/{case_id}/risk/assess`
- `GET /api/v1/cases/{case_id}/risk`
- `GET /api/v1/cases/{case_id}/risk/history`
- `GET /api/v1/cases/{case_id}/risk/delta`
- `GET /api/v1/cases/{case_id}/risk/factors`
- `GET /api/v1/cases/{case_id}/risk/alerts`
- `GET /health`

See [ARCHITECTURE.md](ARCHITECTURE.md) and [docs/development-status.md](docs/development-status.md) for scope and limitations.

The investigator web also provides the current workstation shell, dashboard, manual intake flow, case overview, and operational transaction graph inspector. Wallet, entity, evidence, alert, and report workspaces are capability-ready surfaces backed only where the current API supports them. SAHYOG/NCRP are explicitly marked simulated/not connected, and real-time monitoring is not configured.

## Safety boundary

This system is analysis-only: it never stores private keys, signs transactions, or transfers funds. Attribution is separate from fact, and analytical signals always retain supporting evidence references.
## Phase 7 — RRR Real-Time Retracing

The realtime boundary is implemented with signed Alchemy Address Activity webhook intake, canonical event normalization, PostgreSQL idempotency, case-scoped watch targets, reorg-safe observations, incremental evidence/graph updates, and risk/pattern reassessment hooks. The API and UI report `NOT_CONFIGURED` until `ALCHEMY_API_KEY`, `ALCHEMY_WEBHOOK_ID`, and `ALCHEMY_WEBHOOK_SIGNING_KEY` are configured. WebSocket ingestion and automatic webhook registration are not enabled.

## Phase 8 — Cross-chain intelligence

The cross-chain boundary now supports chain-aware Ethereum/Tron models, a bounded TronGrid adapter, data-driven bridge definitions, explicit observed transfers versus inferred confidence-scored links, persistent cross-chain traces, and investigator APIs/UI. Tron and bridge functionality remain `NOT_CONFIGURED` until approved provider credentials and curated bridge definitions are supplied.
