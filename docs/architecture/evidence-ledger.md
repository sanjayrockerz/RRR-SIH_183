# Evidence ledger and chain of custody

RRR stores blockchain observations as immutable application evidence. Analytical references remain separate from the source observation: a graph, pattern, risk assessment, or report may refer to evidence but cannot replace it.

Each evidence item can receive a SHA-256 `content_hash` derived from canonical JSON containing its case, type, chain, transaction reference, provider, capture time, and metadata. A manifest hashes sorted `(evidence_id, content_hash)` pairs, making its root reproducible regardless of request order. `evidence_chain_events` records append-only custody events with the prior event hash and an event hash.

The hash proves consistency of the captured application record; it does not independently prove that a provider or investigator input was truthful. Authenticated export, legal certification, and actor identity are deliberately outside this slice and require authorization/RBAC plus an approved export workflow.

APIs: `POST /api/v1/cases/{case_id}/evidence/manifest`, `GET /api/v1/cases/{case_id}/evidence/ledger`, `GET /api/v1/cases/{case_id}/evidence/manifests`, `GET /api/v1/cases/{case_id}/evidence/{evidence_id}/chain-of-custody`, and `GET /api/v1/cases/{case_id}/audit-events`.
