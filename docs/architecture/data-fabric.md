# Blockchain data fabric

The data fabric is the provider-independent boundary for historical blockchain observations. BlockchainDataFabric defines address transfers, transaction details, receipts, and block headers; BlockchainProvider remains the application-facing provider contract and Alchemy is only one adapter.

Alchemy transfer pages are followed with pageKey. Every request is bounded by page size, maximum pages, and maximum transactions. A repeated cursor terminates safely. Normalization preserves canonical fields plus a raw reference containing provider, method, retrieval time, provider identifier, and the original payload.

Transfer is the normalized asset movement record. Native and token movements share the model; token rows retain transfer type, contract address, token ID, decimals, and asset label. Persistent transactions represent deduplicated blockchain transactions. transaction_transfers represents one or more asset movements within a transaction.

Receipts, blocks, websocket subscriptions, and webhooks have explicit capability states. Only historical transfer, transaction, receipt, and block retrieval are implemented for Alchemy in Phase 2.
