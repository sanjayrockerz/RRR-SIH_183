# Cross-case intelligence

RRR exposes a conservative read-only relationship view at `GET /api/v1/cases/{case_id}/related`. It links cases only when PostgreSQL contains an exact shared wallet identity (`chain + address`) or shared canonical transaction identity (`chain + tx_hash`). Wallets and transactions remain independent records, so this query does not duplicate or mutate them.

Each result describes the overlap and explicitly states that it is an observed data relationship. The system does not infer common ownership, coordination, fraud, or criminality from address resemblance, labels, timing, or amount similarity. Future confidence-scored leads may be added only with provenance and evidence requirements.
