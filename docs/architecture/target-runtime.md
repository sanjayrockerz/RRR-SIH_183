# Target runtime architecture

RRR should evolve as a modular monolith first, with explicit seams for workers and projections.

```text
Authorized complaint source
  → Case intake adapter
  → Case service
  → PostgreSQL system of record

Blockchain providers / webhooks / indexers
  → Provider registry + capability checks
  → Ingestion gateway
  → Canonical normalizer
  → Evidence ledger + PostgreSQL transaction store
  → Graph projection (optional Neo4j)
  → NetworkX bounded analysis
  → Entity / threat / sanctions enrichment
  → Pattern engine
  → Deterministic risk engine
  → Alert candidate / watch engine
  → Timeline and audit events
  → Investigator UI / evidence-backed reports
```

## Data ownership

- PostgreSQL owns cases, canonical blockchain observations, evidence, assessments, alerts, timelines, and audit records.
- NetworkX is an in-process bounded analytical representation.
- Neo4j, if added, is a rebuildable relationship-intelligence projection, never the only source of truth.
- External providers own their source data; RRR stores provenance and raw references subject to licensing/retention policy.

## Provider routing

Each provider exposes capability state: `SUPPORTED`, `NOT_CONFIGURED`, `UNSUPPORTED`, `SIMULATED`, `UNAVAILABLE`, or `RATE_LIMITED`. A router may select primary/secondary/fallback providers, but it must preserve provider identity and must not merge incompatible observations without an explicit normalization policy.

## Event processing boundary

Synchronous in the MVP: case intake, bounded historical trace, graph analysis, pattern analysis, risk assessment.

Future worker boundary: webhook ingestion acknowledgement, normalization, graph projection, enrichment, pattern/risk reassessment, alerting, report generation. A queue should be introduced only after throughput and retry requirements justify it.

## Trust boundaries

1. External complaint systems are untrusted integrations until authenticated and contractually authorized.
2. Blockchain providers are untrusted external data sources; validate addresses, hashes, timestamps, amounts, and reorg flags.
3. Intelligence providers provide attribution/signals, not canonical blockchain facts.
4. Investigator actions require authenticated actor identity and case authorization.
5. Exports are controlled evidence products and require audit logging.
