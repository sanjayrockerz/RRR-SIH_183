# Multi-Chain Data Model

Common transaction and transfer fields remain normalized through `Transfer`, while chain-specific provider payloads remain under `raw_reference`. `ChainAddress`, `AssetIdentity`, and `AssetMapping` retain network-specific identity and provenance. Entity identity is separate from address identity; cross-chain entity joins require source-backed `entity_addresses` records.
