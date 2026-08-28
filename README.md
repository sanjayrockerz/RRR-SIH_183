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
- Evidence ledger with canonical SHA-256 observation hashes, deterministic manifests, and append-only custody events.
- Evidence-backed immutable report snapshots with content hashes and explicit limitations.
- Explicit capability states for historical, simulated, live, unsupported, and not-configured integrations.
- Opt-in signed JWT authentication boundary with explicit local-development and not-configured states.

## Current capability boundary

The current release is historical Ethereum analysis through Alchemy. SAHYOG/NCRP, real-time ingestion, cross-chain tracing, ML risk scoring, authentication/SSO, and automated VASP communication are architectural extension points, not falsely represented live features.

## Quick start

1. Recommended full stack: `docker compose up --build`.
2. For native development, copy `.env.example` to `.env`, activate the virtual environment, and install `apps/api/requirements.txt`.
3. Start FastAPI from the repository root: `uvicorn app.main:app --host 0.0.0.0 --port 8000 --app-dir apps/api`.
4. Start the web app in a second terminal: `cd apps/investigator-web && npm install && npm run dev`.

The API uses PostgreSQL as its source of truth. On startup it applies ordered migrations from `infrastructure/postgres` and records applied versions in `schema_migrations` (set `DATABASE_AUTO_MIGRATE=false` if migrations are managed externally). Attribution remains source-backed and does not establish ownership or criminal involvement.

## API

- `POST /api/v1/cases`
- `GET /api/v1/cases`
- `PATCH /api/v1/cases/{case_id}`
- `POST /api/v1/cases/{case_id}/close`
- `POST /api/v1/cases/{case_id}/reopen`
- `POST /api/v1/cases/{case_id}/wallets`
- `POST /api/v1/cases/{case_id}/transactions`
- `GET /api/v1/cases/{case_id}`
- `GET /api/v1/wallets/{chain}/{address}`
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
- `GET /api/v1/system/status`
- `GET /api/v1/auth/status`
- `GET /api/v1/providers`
- `GET /api/v1/entities/{entity_id}/attributions`
- `GET /api/v1/attribution-sources`
- `GET /api/v1/addresses/{chain}/{address}/sanctions`
- `POST /api/v1/cases/{case_id}/cyber/screen`
- `GET /api/v1/cases/{case_id}/cyber/screening`
- `GET /api/v1/intelligence/sources`
- `GET /api/v1/intelligence/indicators`
- `GET /api/v1/contracts/{chain}/{address}/security`
- `POST /api/v1/cases/{case_id}/evidence/manifest`
- `GET /api/v1/cases/{case_id}/evidence/ledger`
- `GET /api/v1/cases/{case_id}/evidence/manifests`
- `GET /api/v1/cases/{case_id}/evidence/{evidence_id}/chain-of-custody`
- `POST /api/v1/cases/{case_id}/reports`
- `GET /api/v1/cases/{case_id}/reports`
- `GET /api/v1/cases/{case_id}/reports/{report_id}`
- `GET /api/v1/cases/{case_id}/audit-events`
- `GET /api/v1/cases/{case_id}/related`
- `POST /api/v1/cases/{case_id}/alerts/{alert_id}/review`
- `GET /api/v1/cases/{case_id}/alerts/{alert_id}/reviews`

See [ARCHITECTURE.md](ARCHITECTURE.md) and [docs/development-status.md](docs/development-status.md) for scope and limitations.

The investigator web also provides the current workstation shell, dashboard, manual intake flow, persisted case reopening, evidence-backed wallet intelligence lookup, case overview, and operational transaction graph inspector. Entity, evidence, alert, and report workspaces are capability-ready surfaces backed only where the current API supports them. SAHYOG/NCRP are explicitly marked simulated/not connected, and real-time monitoring is not configured.

## Safety boundary

This system is analysis-only: it never stores private keys, signs transactions, or transfers funds. Attribution is separate from fact, and analytical signals always retain supporting evidence references.

## Phase G - Realtime operations

Realtime webhook deliveries retain processing attempts and can enter `RETRY_PENDING` or `DEAD_LETTER` states. Operators can inspect the failure queue and explicitly replay an event. Background queue workers, confirmation-depth reconciliation, and production access control remain disabled until the deployment environment is configured.
## Phase 7 — RRR Real-Time Retracing

The realtime boundary is implemented with signed Alchemy Address Activity webhook intake, canonical event normalization, PostgreSQL idempotency, case-scoped watch targets, reorg-safe observations, incremental evidence/graph updates, and risk/pattern reassessment hooks. The API and UI report `NOT_CONFIGURED` until `ALCHEMY_API_KEY`, `ALCHEMY_WEBHOOK_ID`, and `ALCHEMY_WEBHOOK_SIGNING_KEY` are configured. WebSocket ingestion and automatic webhook registration are not enabled.

## Phase 8 — Cross-chain intelligence

The cross-chain boundary now supports chain-aware Ethereum/Tron models, a bounded TronGrid adapter, data-driven bridge definitions, explicit observed transfers versus inferred confidence-scored links, persistent cross-chain traces, and investigator APIs/UI. Tron and bridge functionality remain `NOT_CONFIGURED` until approved provider credentials and curated bridge definitions are supplied.
