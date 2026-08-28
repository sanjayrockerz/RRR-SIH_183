# Provider registry

`BlockchainProviderRegistry` selects the blockchain data adapter by chain. Current adapters are Alchemy Ethereum and TronGrid. The realtime boundary uses the Alchemy webhook adapter. Provider capabilities expose configuration state; health probes make a bounded network request when credentials are configured.

Provider secrets are backend-only environment variables. The registry does not expose credentials to React. Optional commercial attribution, sanctions and threat providers must implement an independent source/provenance boundary before being enabled.
