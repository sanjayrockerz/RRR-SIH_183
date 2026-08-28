# Sanctions screening

RRR treats sanctions screening as a source-backed lookup, not as a criminality classifier. The current engine supports exact address matches against explicitly persisted records with a chain constraint where supplied.

Results:

- `DIRECT_MATCH`: exact normalized address match in a configured record.
- `NO_MATCH`: no exact match in the configured records; this is not a clearance.
- `NOT_CONFIGURED`: no approved source is available, so no screening conclusion is made.
- `UNKNOWN`: reserved for future provider failures or unresolved source results.

Each case screening is persisted as a screening run with its source outcome, timestamp, explanation, and match records. Dataset version and source reference remain attached to every sanctions record. Indirect exposure, fuzzy matching, list-name inference, and sanctions conclusions are not implemented.
