# Evidence ledger

Risk factors retain references to the same canonical evidence chain used by tracing and pattern intelligence:

`transaction → graph edge → evidence → pattern observation → risk factor → risk assessment`

PostgreSQL stores typed risk assessment and factor records, plus normalized joins for factor/evidence, factor/pattern, factor/entity, and assessment/transaction references. Assessment records are immutable and historical versions are never overwritten.

The ledger is a canonical investigation record, not a replacement for an explorer or the source blockchain. Provider, transaction hash, block, timestamp, asset, and retrieval provenance remain in the underlying transaction/evidence records.
