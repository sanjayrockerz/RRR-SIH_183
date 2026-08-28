# Neo4j relationship projection

Neo4j is an optional relationship-intelligence projection. It is not a replacement for PostgreSQL and does not become authoritative merely because a relationship exists in the graph.

## Ownership

- PostgreSQL stores canonical cases, transactions, transfers, evidence, trace runs, patterns, risks, alerts, and timelines.
- NetworkX performs bounded in-process trace/path/metric analysis.
- Neo4j projects relationships for bounded neighborhood and path queries.

## Idempotency

Wallet nodes are keyed by `chain:address`. Transaction nodes are keyed by a deterministic hash of `transaction`, chain, and transaction hash. Transfer relationships use a deterministic hash of case, chain, transaction, endpoints, asset, amount, and hop. Replaying a trace therefore uses `MERGE` and does not create duplicate relationships.

## Evidence

Projected transfer relationships preserve transaction hash, chain, asset, amount, timestamp, block, direction, provider, and evidence ID. Transaction nodes link to evidence nodes using `SUPPORTED_BY`. Missing evidence IDs are not invented.

## Failure policy

Neo4j connection or projection failure is observable in logs and capability status, but does not roll back or replace the PostgreSQL trace. An investigator can explicitly retry projection with `POST /api/v1/graph/{case_id}/project` after Neo4j becomes available.

Realtime integration uses `GraphProjectionService.project_incremental` with the canonical `RealtimeEvent` and the persisted graph-edge/evidence identifiers produced by the application service. The event is projected as a bounded one-edge batch using the same idempotent relationship keys. This is an optional projection update, not a second source of truth; an unavailable Neo4j instance does not prevent the canonical realtime observation from being stored or analyzed.

## Security and scale

Credentials are backend-only environment variables. Query depth is bounded to five for neighborhood queries and twelve for shortest-path traversal. Case filters are applied in Cypher. Production deployment still requires authentication, authorization, TLS, backups, and projection monitoring.
