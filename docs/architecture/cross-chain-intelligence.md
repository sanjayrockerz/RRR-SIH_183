# Cross-Chain Intelligence

Phase 8 adds chain-aware identity and evidence-backed cross-chain relationships without changing the Phase 0–7 Ethereum contracts.

## Chain registry

`ChainRegistry` currently describes Ethereum and Tron. Node identity is `chain:lowercase(address)`, so identical address text on two networks is never treated as the same on-chain address. Ethereum uses the existing Alchemy adapter. Tron uses the bounded TronGrid adapter and remains `NOT_CONFIGURED` until `TRONGRID_API_KEY` is present.

## Graph semantics

On-chain transfers remain `OBSERVED`. Bridge-mediated relationships are separate `CROSS_CHAIN_LINK` edges and are always `INFERRED` with an explicit confidence level, score, reasons, source, and evidence IDs. An unresolved bridge interaction has no destination address asserted.

## Limits

Cross-chain analysis has separate hop, cross-chain-hop, node, edge, bridge-interaction, transaction, and duration limits. A result can be `PARTIAL`; it is never silently presented as a complete trace.
