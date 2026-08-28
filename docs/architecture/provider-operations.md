# Provider operations

RRR selects a blockchain adapter through `BlockchainProviderRegistry`. Application services ask for a provider by canonical `Chain`; they do not import Alchemy or TronGrid directly. This keeps ingestion, tracing, and future entity/cyber-intelligence services provider-independent.

## Capability state

`SUPPORTED`, `NOT_CONFIGURED`, `UNSUPPORTED`, `UNAVAILABLE`, and `RATE_LIMITED` are operational states. `GET /api/v1/providers` exposes the registry view without secrets. The endpoint reports configuration and declared capability state; it is not a continuous network health probe.

## Current adapters

- Alchemy Ethereum: historical address transfers, transaction, receipt, block, and token-transfer normalization when `ALCHEMY_API_KEY` is configured. Address transfers use bounded `pageKey` pagination.
- TronGrid: bounded historical TRC20 transfer, transaction, receipt, and block adapter when `TRONGRID_API_KEY` is configured. It remains credential-gated and is not represented as live ingestion.

Both HTTP adapters use an environment-configured timeout and bounded retries for transient timeout, network, rate-limit, and server failures. Raw provider payloads remain inside normalized observation `raw_reference` fields and are never sent to the frontend as credentials.

## Operational limitation

Provider status currently describes declared configuration/capability state. Continuous latency, error-rate, circuit-breaker, and credential-validation telemetry are intentionally a later operations slice. A provider failure is translated at the API boundary into a safe error rather than silently returning fixture data.
