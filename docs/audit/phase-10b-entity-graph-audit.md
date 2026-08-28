# Phase 10B entity, ledger, and graph audit

Audit date: 2026-08-28. This inventory distinguishes persisted evidence from development-only intelligence.

| Surface | API / persistence | Finding before change | Corrective work | State |
|---|---|---|---|---|
| Transaction ledger | `case_transactions` / PostgreSQL transactions, transfers, evidence | Real records existed but no server-side filters were exposed. | Added bounded chain, asset, status, wallet/direction, time, transaction/address search and pagination parameters. | CONNECTED |
| Entity/VASP intelligence | entities, attribution sources, address attributions | Resolver and persistence existed but no versioned in-repository curated development data or case-scoped entity reads. | Added a versioned development dataset, migration-backed provenance, case and wallet entity APIs. | CONNECTED (CURATED INTELLIGENCE) |
| Nearest VASP | `NearestEntityResolver` over persisted trace | The resolver existed but case summary did not expose the outcome. | Case summary now includes source-backed `vasp_exposure` only when an attributed VASP/exchange address is observed. | CONNECTED |
| Graph | persisted graph edges, trace reconstruction, optional Neo4j | The UI recalculates layout on render; it has no persisted layout endpoint. | Added `case_graph_layouts` and case-scoped GET/POST layout APIs. | PARTIAL |
| Entity workspace | `/entities` catalog | Real catalog was global rather than case scoped; provenance was not sufficiently prominent. | Added case-scoped entity endpoint. Workspace wiring remains pending. | PARTIAL |

## Integrity and language safeguards

- `Example Exchange — Development Attribution` is a **development-only curated fixture** for synthetic address `0x9999…9999`. It is not a claim about a real exchange or address owner.
- Each attribution preserves source, version, confidence, address, chain, and source reference.
- PostgreSQL remains the system of record. Neo4j remains optional graph projection/query infrastructure.
- A provider that is unavailable must remain unavailable rather than appearing as an empty array, zero count, or no-match result.

## Remaining Phase 10B work

The existing graph still needs direct UI wiring for its new layout API, node drag/save/reset affordances, case entity panels, and selected-pattern edge highlighting. This audit does not call those items complete.
