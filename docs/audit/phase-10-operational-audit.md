# Phase 10 operational audit

Audit date: 2026-08-28. This inventory records runtime-facing behaviour, not whether a component merely exists.

| UI surface | Backend endpoint | Database source | Real/Synthetic | Interactive | Status |
|---|---|---|---|---|---|
| Command center | `/dashboard/summary`, `/system/status`, `/providers` | cases, wallets, alerts, watches | persisted + provider state | navigation/new case | PARTIAL |
| Case registry | `/cases` | cases, case_wallets, case_transactions | persisted | open case | CONNECTED |
| Connected intake | `/cases`, `/wallets`, `/traces` | cases, wallets, traces, evidence | fixture or configured provider | create/trace | CONNECTED |
| Case workspace | `/cases/{id}`, patterns/risk/evidence/timeline routes | case aggregate tables | persisted | workspace navigation | PARTIAL |
| Transaction ledger | `/cases/{id}/transactions` | transactions, transfers, evidence | persisted | filter, sort, drawer, evidence/graph links | CONNECTED |
| Graph | `/cases/{id}/graph`, Neo4j graph routes | trace_runs, graph_edges, Neo4j projection | persisted / optional Neo4j | pan, zoom, inspect | PARTIAL |
| Wallet intelligence | `/wallets/{chain}/{address}` | wallets, cases, evidence | persisted | lookup | CONNECTED |
| Entity/VASP | `/entities`, attribution routes | entities, attributions, sources | curated/optional providers | browse | PARTIAL |
| Threat/sanctions | screening/source routes | sanctions and cyber intelligence tables | configured/unknown | browse/screen | PARTIAL |
| Pattern intelligence | case pattern routes | pattern observations/evidence | persisted | detail navigation | CONNECTED |
| Risk intelligence | case risk/history/factors routes | risk assessments/factors/evidence | persisted | detail navigation | CONNECTED |
| Realtime retracing | SSE, watches, synthetic controls | realtime events, applications, changes, alerts, timeline | DEVELOPMENT_SYNTHETIC or live provider | play/pause/step | CONNECTED |
| Evidence ledger | evidence/ledger/manifest routes | evidence, custody, manifests | persisted | view/create manifest | CONNECTED |
| Reports | report routes | report snapshots | persisted | generate/view | CONNECTED |
| Mobile foundation | `/mobile/*`, shared SSE | same canonical tables | persisted / explicit synthetic | API contract | CONNECTED |

## Highest-impact findings addressed in this phase

1. Transaction workspace previously reused a graph and had no canonical ledger endpoint. It now reads a case-scoped transaction, transfer and evidence ledger directly from PostgreSQL.
2. The synthetic command center had a fixed implicit count and seed. It now has visible scenario, seed, speed and event-count controls (10/50/100/500/1000) that invoke the canonical realtime pipeline.
3. Repeated watch creation exposed a persistence defect on conflict; the repository now returns the existing persisted watch rather than `None`.

## Explicit limitations

- Alchemy, commercial attribution, OFAC and threat-intelligence results remain `NOT_CONFIGURED` unless their credentials/datasets are supplied. The UI must not infer clean/no-match from these states.
- Neo4j is an optional projection/query capability; PostgreSQL remains the canonical source of truth.
- No native APK is included. The mobile API is a shared-backend foundation for a future client.
