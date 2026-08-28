# Neo4j integration

PostgreSQL remains authoritative. `Neo4jClient`, `Neo4jGraphRepository` and `GraphProjectionService` provide an optional projection of cases, wallets, transactions and evidence-linked relationships. Projection identifiers are deterministic and writes are intended to be idempotent.

Supported query boundaries are bounded neighborhood and shortest-path reads. If Neo4j is absent or unavailable, NetworkX/PostgreSQL analysis remains the fallback analytical path and the capability is reported as `NOT_CONFIGURED` or `UNAVAILABLE`.
