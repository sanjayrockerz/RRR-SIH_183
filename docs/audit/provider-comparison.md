# Provider and intelligence-source comparison

Updated: 2026-08-26. Capability statements below are based on provider documentation or official product pages; commercial product availability, limits, and pricing must be confirmed during procurement.

| Source | Category | Useful contribution to RRR | Current integration | Access / limitation |
|---|---|---|---|---|
| Alchemy | Blockchain data + webhook provider | EVM historical transfers, metadata, receipts/RPC, Address Activity webhook | Ethereum adapter and signed webhook boundary | Key/configuration required; webhook registration is external; not attribution |
| Etherscan | Explorer/indexer API | Ethereum account transactions, token transfer and contract/explorer data | Not integrated | API key and rate limits; should be fallback/verification, not silently merged with Alchemy |
| TronGrid | Blockchain data provider | Tron historical TRC20 transfer boundary | Partial adapter | `TRONGRID_API_KEY` required; no realtime adapter in RRR |
| Chainalysis | Commercial blockchain intelligence | Entity attribution, investigative graphing, cross-chain and illicit-exposure intelligence | Not configured | Commercial access; vendor intelligence must remain provenance-labeled |
| TRM Labs BLOCKINT API | Commercial blockchain intelligence | Address behavior, exposure, flows, transaction history and multi-chain intelligence | Not configured | Commercial/demo access; exact API contract and entitlement required |
| Elliptic | Commercial compliance/investigation intelligence | Screening, exposure, entity/VASP intelligence and cross-chain risk | Not configured | Commercial access; scores are vendor outputs, not RRR rule scores |
| Bitquery | Blockchain indexer/query provider | Multi-chain indexed queries, transfers, balances and GraphQL-style extraction | Not configured | Verify chain coverage and query limits before selecting as fallback |
| GoldRush/Covalent | Blockchain data provider | Unified historical balances/transactions across supported chains | Not configured | Coverage, pagination and commercial limits require validation |
| Moralis | Blockchain data/API platform | Address, token, NFT and chain data | Not configured | Provider-specific schemas require canonical normalization |
| Blockchair | Explorer/indexer API | Public blockchain explorer/indexed data for supported chains | Not configured | Coverage varies by chain; not attribution or threat intelligence |
| Chainabuse | Threat-intelligence/reporting source | Community scam/fraud reports where accessible and legally appropriate | Not configured | Reports require source, timestamp, moderation/context and confidence; do not treat a report as adjudication |
| OFAC SLS | Official sanctions source | Versioned SDN and consolidated sanctions data | Not integrated | Public data download; wallet screening requires a validated address/entity mapping method |
| GoPlus Security | Contract/token/security intelligence | Token and address security indicators where API entitlement supports them | Not configured | Separate contract/token findings from wallet risk; verify official API terms and coverage |

## Recommended routing

1. Primary chain data: Alchemy for supported EVM historical and webhook activity.
2. Secondary chain data: TronGrid only after credentialed, bounded Tron tests pass.
3. Data fallback: add Etherscan/Bitquery behind a provider router only when a concrete failure/coverage policy exists.
4. Attribution/intelligence: commercial providers are optional enrichment sources, never replacements for canonical observed transactions.
5. Sanctions: versioned OFAC ingestion plus optional commercial screening; preserve direct/indirect/unknown distinctions.
6. Threat intelligence: curated, source-backed reports first; provider adapters later.
7. Contract security: separate `ContractSecurityProvider` and persistence from wallet risk.

## Official references

- [Alchemy Address Activity Webhook](https://www.alchemy.com/docs/reference/address-activity-webhook)
- [Alchemy Transfers API](https://www.alchemy.com/docs/data/transfers-api/transfers-endpoints/alchemy-get-asset-transfers)
- [Alchemy Webhooks Quickstart and signatures](https://www.alchemy.com/docs/docs/reference/notify-api-quickstart)
- [Chainalysis Reactor](https://www.chainalysis.com/product/reactor/)
- [TRM BLOCKINT API](https://www.trmlabs.com/blockchain-intelligence-platform/blockint-api)
- [Elliptic platform](https://www.elliptic.co/)
- [OFAC Sanctions List Service](https://ofac.treasury.gov/sanctions-list-service)

## Non-negotiable provenance fields

Every enrichment record should retain provider, source/reference, retrieved time, observed time, raw reference, source version, confidence, expiration, and the affected chain/address/transaction. Provider data must never overwrite a canonical blockchain observation.
