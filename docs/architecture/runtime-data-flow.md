# Runtime data flow

RRR keeps PostgreSQL as the system of record. Provider adapters acquire blockchain observations; services normalize and analyze them; NetworkX performs bounded local graph analysis; Neo4j is an optional rebuildable relationship projection.

```text
case + wallet
  -> provider registry
  -> normalized transfers
  -> PostgreSQL transactions/transfers/evidence
  -> bounded NetworkX trace
  -> persisted graph edges
  -> pattern observations
  -> risk assessment/delta
  -> realtime watch
  -> verified event
  -> transaction/evidence/graph update
  -> pattern/risk reassessment
  -> alert/timeline/report
```

Every stage is bounded and source-labelled. Missing dependencies produce explicit unavailable/configuration states and never generate substitute blockchain facts.
