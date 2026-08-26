# ADR 0002: Persist independent investigation entities and blockchain observations

## Decision

Cases, wallets, and canonical transactions are persisted independently. Case-specific relationships connect them through `case_wallets` and `case_transactions`; trace edges and evidence reference the canonical transaction.

## Rationale

The same wallet or transaction can appear in multiple investigations. A unique `(chain, tx_hash)` transaction boundary prevents duplicate blockchain observations while preserving case-specific context and relation types.
