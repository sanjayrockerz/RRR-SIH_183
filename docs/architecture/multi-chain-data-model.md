# Multi-Chain Data Model

Address normalization is chain-specific. Ethereum hexadecimal addresses are normalized to lowercase for identity lookups. Tron Base58 addresses preserve their original case because case changes the address representation. The trace service, NetworkX builder, PostgreSQL graph-edge persistence, Neo4j projection, watches, and cross-chain registry all apply the same rule. A node identity is therefore `chain:normalized_address`; equal text on different chains is never merged.

Common transaction and transfer fields remain normalized through `Transfer`, while chain-specific provider payloads remain under `raw_reference`. `ChainAddress`, `AssetIdentity`, and `AssetMapping` retain network-specific identity and provenance. Entity identity is separate from address identity; cross-chain entity joins require source-backed `entity_addresses` records.
